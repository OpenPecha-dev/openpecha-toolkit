import copy
import shutil
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Union

from git import Repo

from openpecha import blupdate, config
from openpecha.core import ids
from openpecha.core.annotations import BaseAnnotation, Span
from openpecha.core.layer import Layer, LayerEnum, PechaMetadata, SpanINFO
from openpecha.github_utils import create_release
from openpecha.storages import GithubStorage, Storage, commit_and_push
from openpecha.utils import download_pecha, dump_yaml, load_yaml, load_yaml_str


class OpenPecha:
    """
    The main abstract class representing an opf. The methods to implement are:
    - read_meta_file()
    - read_base_file(base_name)
    - read_layers_file(base_name, layer_name)
    - _read_components()
    - read_index_file()
    """

    def __init__(
        self,
        bases: Dict[str, str] = None,
        layers: Dict[str, Dict[LayerEnum, Layer]] = None,
        index: Layer = None,
        meta: PechaMetadata = None,
        metadata: PechaMetadata = None,
        assets: Dict[str, List[Union[str, Path]]] = None,
        components: Dict[str, List[Layer]] = None,
        pecha_id: str = None,
    ):
        self._pecha_id = pecha_id
        self.bases = bases if bases else {}
        self.layers = layers if layers else defaultdict(dict)
        self._meta = self.__handle_old_metadata_attr(meta, metadata)
        self._index = index
        self.assets = assets if assets else {}
        self._base_names_list = []
        self._components = components if components else {}
        self.current_base_order = 1

    def __str__(self):
        return f"OpenPecha:{self.pecha_id}"

    def __handle_old_metadata_attr(self, old, new):
        if not old and not new:
            return

        if new:
            return new

        warnings.warn(
            "use `metadata` attr instead of `meta` to set pecha metadata",
            DeprecationWarning,
            stacklevel=3,
        )
        return old

    @property
    def about(self):
        if not self.meta.source_metadata:
            return ""
        source_metadata = []
        descriptive_labels = ["title", "author", "id"]
        for label, info in self.meta.source_metadata.items():
            if label in descriptive_labels:
                if isinstance(info, list):
                    cur_info = f"{label}: {' '.join(info)}"
                    source_metadata.append(cur_info)
                else:
                    cur_info = f"{label}: {info}"
                    source_metadata.append(cur_info)
        return ", ".join(source_metadata)

    def reset_base_and_layers(self):
        self.bases = {}
        self.layers = defaultdict(dict)

    @property
    def pecha_id(self) -> str:
        if self._pecha_id:
            return self._pecha_id
        self._pecha_id = self.meta.id
        return self._pecha_id

    @property
    def meta(self) -> PechaMetadata:
        if self._meta:
            return self._meta
        mf = self.read_meta_file()
        if mf is not None:
            self._meta = PechaMetadata.parse_obj(mf)
            return self._meta
        self._meta = PechaMetadata.parse_obj({})
        return self._meta

    @property
    def index(self) -> Layer:
        if self._index:
            return self._index
        idxf = self.read_index_file()
        if idxf is not None:
            self._index = Layer.parse_obj(idxf)
        return self._index

    @property
    def base_names_list(self) -> List[str]:
        if self.bases:
            self._base_names_list = list(self.bases.keys())

        if "bases" in self.meta in self.meta.bases:
            self._base_names_list = list(self.meta.bases.keys())

        if not self._base_names_list:
            self._base_names_list = self._read_base_names()

        return self._base_names_list

    @property
    def components(self) -> Dict[str, List[LayerEnum]]:
        if self._components:
            return self._components
        self._components = self._read_components()
        return self._components

    @property
    def is_private(self):
        if self.meta.source_metadata:
            if self.meta.source_metadata.get(
                "geo_restriction", []
            ) or self.meta.source_metadata.get("restrictedInChina", False):
                return True
            if (
                self.meta.source_metadata.get("access", "")
                != "http://purl.bdrc.io/admindata/AccessOpen"
            ):
                return True
        return False

    def _get_base_name(self) -> str:
        return ids.get_base_id()

    def _set_base_metadata(self, base_name: str, metadata: Dict) -> None:
        metadata.update({"base_file": f"{base_name}.txt"})
        if not hasattr(self.meta, "bases"):
            self.meta.bases = {}
        self.meta.bases[base_name] = metadata

    def get_base(self, base_name: str) -> str:
        if base_name in self.bases:
            return self.bases[base_name]
        self.bases[base_name] = self.read_base_file(base_name)
        return self.bases[base_name]

    def get_base_metadata(self, base_name: str) -> str:
        return self.meta.bases.get(base_name)

    def set_base(
        self,
        content: str,
        base_name: str = None,
        metadata: Dict = {},
        update_layer_coordinates=True,
    ) -> str:
        """Create new base with `content` if `base_name` is not
        given otherwise overwrites it and return base_name.
        """
        if not base_name:
            base_name = self._get_base_name()
        if base_name in self.bases:
            if update_layer_coordinates:
                blupdate.update_single_base(self, base_name, content)
            self.bases[base_name] = content
        else:

            self.bases[base_name] = content
            self._set_base_metadata(base_name, copy.deepcopy(metadata))
        return base_name

    def get_layers(self, base_name: str) -> Layer:
        for layer_name in self.components[base_name]:
            yield self.get_layer(base_name, layer_name)

    def get_layer(self, base_name: str, layer_name: LayerEnum) -> Layer:
        if base_name in self.layers and layer_name in self.layers[base_name]:
            layer = self.layers[base_name][layer_name]
            if layer:
                return layer

        layer_dict = self.read_layers_file(base_name, layer_name)
        if layer_dict:
            layer = Layer.parse_obj(layer_dict)
        else:
            layer = Layer(annotation_type=layer_name)
        self.layers[base_name][layer_name] = layer
        return layer

    def update_metadata(self):
        self.meta.update_last_modified_date()

    def set_layer(self, base_name: str, layer: Layer):
        if base_name not in self.bases:
            raise ValueError(f"set base for {base_name} first")

        self.layers[base_name][layer.annotation_type] = layer

    def __find_span_layers(
        self, base_name: str, span: Span, layers: List[LayerEnum]
    ) -> Dict[LayerEnum, List[BaseAnnotation]]:
        result = defaultdict(list)
        for layer_name in layers:
            if layer_name not in self.components[base_name]:
                result[layer_name] = []

            layer = self.get_layer(base_name, layer_name)
            for _, ann in layer.get_annotations():
                is_ann_found = False
                if ann.span.start >= span.start and ann.span.end <= span.end:
                    is_ann_found = True
                elif ann.span.end >= span.start and ann.span.start < span.start:
                    is_ann_found = True
                    ann.span.start = span.start
                elif ann.span.start <= span.end and ann.span.end > span.end:
                    is_ann_found = True
                    ann.span.end = span.end

                if is_ann_found:
                    ann.span.start -= span.start
                    ann.span.end -= span.start
                    result[layer_name].append(ann)

        return result

    def get_span_info(
        self, base_name: str, span: Span, layers: List[LayerEnum] = []
    ) -> SpanINFO:
        base_str = self.get_base(base_name)
        span_str = base_str[span.start : span.end + 1]  # noqa
        layers = layers if layers else self.components[base_name]
        span_layers = self.__find_span_layers(base_name, span, layers)
        return SpanINFO(text=span_str, layers=span_layers, metadata=self.meta)


class OpenPechaFS(OpenPecha):
    """Class to represent opf pecha on file-system.

    Attributes:
        pecha_id(str): id of openpecha pecha.
        path (str): path to .opf directory.
    """

    def __init__(self, path: str = None, pecha_id: str = None, **kwargs):
        self._opf_path = Path(path) if path else None
        super().__init__(pecha_id=pecha_id, **kwargs)

    @staticmethod
    def _mkdir(path: Path):
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def opf_path(self) -> Path:
        return self._opf_path

    @property
    def base_path(self) -> Path:
        return self.opf_path / "base"

    @property
    def layers_path(self) -> Path:
        return self.opf_path / "layers"

    @property
    def meta_fn(self) -> Path:
        return self.opf_path / "meta.yml"

    @property
    def index_fn(self) -> Path:
        return self.opf_path / f"{LayerEnum.index.value}.yml"

    @property
    def assets_path(self) -> Path:
        return self.opf_path / "assets"

    def read_base_file(self, base_name: str) -> str:
        base_fn = self.base_path / f"{base_name}.txt"
        if base_fn.is_file():
            return base_fn.read_text(encoding="utf-8")

    def read_layers_file(
        self, base_name: str, layer_name: LayerEnum
    ) -> Union[Dict, None]:
        layer_fn = self.layers_path / base_name / f"{layer_name.value}.yml"
        if layer_fn.is_file():
            return load_yaml(layer_fn)

    def read_meta_file(self) -> Dict:
        if self.meta_fn.is_file():
            return load_yaml(self.meta_fn)

    def read_index_file(self) -> Dict:
        if self.index_fn.is_file():
            return load_yaml(self.index_fn)

    def _read_base_names(self):
        return [base.stem for base in self.base_path.iterdir()]

    def _read_components(self):
        res = {}
        for vol_dir in self.layers_path.iterdir():
            all_layers = set(layer.value for layer in LayerEnum)
            res[vol_dir.name] = list(
                map(
                    lambda fn: LayerEnum(fn.stem),
                    (
                        layer_fn
                        for layer_fn in vol_dir.iterdir()
                        if layer_fn.stem in all_layers
                    ),
                )
            )
        return res

    def save_meta(self):
        OpenPechaFS._mkdir(self.base_path)
        dump_yaml(self.meta.dict(exclude_none=True), self.meta_fn)

    def save_single_base(self, base_name: str, content: str = None):
        if not content:
            content = self.bases[base_name]
        base_fn = OpenPechaFS._mkdir(self.base_path) / f"{base_name}.txt"
        if content:
            base_fn.write_text(content, encoding="utf-8")
        else:
            if base_fn.exists():
                base_fn.unlink()

    def save_base(self):
        for base_name, content in self.bases.items():
            self.save_single_base(base_name, content)

    def save_layer(self, base_name: str, layer_name: LayerEnum, layer: Layer):
        layer_fn = (
            OpenPechaFS._mkdir(self.layers_path / base_name) / f"{layer_name.value}.yml"
        )
        dump_yaml(layer.dict(exclude_none=True), layer_fn)
        return layer_fn

    def save_layers(self):
        for base_name, base_layers in self.layers.items():
            for layer_name, layer in base_layers.items():
                self.save_layer(base_name, layer_name, layer)

    def save_index(self):
        if self.index is None:
            return
        try:
            dump_yaml(self.index.dict(exclude_none=True), self.index_fn)
        except FileNotFoundError:
            pass

    def save_assets(self):
        for assets_type, content in self.assets.items():
            assets_type_dir = self.assets_path / assets_type
            assets_type_dir.mkdir(parents=True, exist_ok=True)
            for asset_fn in content:
                asset_fn = Path(asset_fn)
                dest_fn = assets_type_dir / asset_fn.name
                shutil.copyfile(str(asset_fn), str(dest_fn))

    def save(self, path: str = None):
        saved_opf_path = self._opf_path
        if path is not None:
            self._opf_path = Path(path)
        OpenPechaFS._mkdir(self._opf_path)
        self.save_base()
        self.save_layers()
        self.save_index()
        self.save_meta()
        self.save_assets()
        self._opf_path = saved_opf_path

    def update_base(self, base_name: str, content: str):
        self.set_base(content, base_name)
        self.save_single_base(base_name)
        self.update_metadata()

    def update_layer(self, base_name: str, layer_name: LayerEnum, layer: Layer):
        old_layer = self.get_layer(base_name, layer_name)
        old_layer.bump_revision()
        old_layer.annotations = layer.annotations
        self.save_layer(base_name, layer_name, old_layer)
        self.update_metadata()

    def reset_layer(self, base_name: str, layer_name: LayerEnum):
        layer = self.get_layer(base_name, layer_name)
        layer.reset()
        self.save_layer(base_name, layer_name, layer)
        self.layers[base_name][layer_name] = None

    def reset_layers(self, base_name: str, exclude: List[LayerEnum] = []):
        for layer_name in self.components[base_name]:
            if layer_name in exclude:
                continue
            self.reset_layer(base_name, layer_name)


class OpenPechaGitRepo(OpenPechaFS):
    """
    Class to represent opf pecha on file-system, connected to
    the OpenPecha-Data github organization

    Note:
        Either use pecha_id or `path` attribute to create
        instance, `pecha_id` for downloading/updating pecha and
        `path` for local pecha.

    Attributes:
        pecha_id(str): id of openpecha pecha.
        path (str): path to local pecha root or pecha .opf path.
        storage (Storage): storage for distant interaction.
    """

    def __init__(
        self, pecha_id: str = None, path: str = None, storage: Storage = None, **kwargs
    ):
        self._opf_path = OpenPechaGitRepo.get_opf_path(pecha_id, path)
        self.storage = storage
        super().__init__(pecha_id=pecha_id, path=self._opf_path, **kwargs)

    @staticmethod
    def get_opf_path(pecha_id, path: str) -> Path:
        """convert pecha path to pecha's opf path"""
        if not pecha_id and not path:
            return

        if not path:
            path = download_pecha(pecha_id)

        path = Path(path)
        if path.name.endswith(".opf"):
            return path
        path = path / f"{path.name}.opf"
        if not path.is_dir():
            raise FileNotFoundError(f"Pecha not found at: {path}")
        return path

    @property
    def pecha_path(self) -> Path:
        if self._opf_path:
            return self._opf_path.parent
        return self.output_dir / self.pecha_id

    @property
    def opf_path(self) -> Path:
        if self._opf_path:
            return self._opf_path
        self._opf_path = self.pecha_path / f"{self.pecha_id}.opf"
        return self._opf_path

    def publish(
        self, asset_path: Path = None, asset_name: str = None, branch: str = None
    ):
        asset_paths = []
        if not self.storage:
            self.storage = GithubStorage()
        if self.storage.is_git_repo(self.pecha_path):
            local_repo = Repo(self.pecha_path)
            commit_and_push(repo=local_repo, message="Pecha update", branch=branch)
        else:
            self.storage.add_dir(
                path=self.pecha_path,
                description=self.about,
                is_private=self.is_private,
                branch=branch,
            )

        # Publishing assets in release
        if asset_path:
            repo_name = self.pecha_id
            shutil.make_archive(asset_path.parent / asset_name, "zip", asset_path)
            asset_paths.append(f"{asset_path.parent / asset_name}.zip")
            create_release(
                repo_name,
                prerelease=False,
                asset_paths=asset_paths,
                org=self.storage.org_name,
                token=self.storage.token,
            )
            (asset_path.parent / f"{asset_name}.zip").unlink()

    def save(self, output_path: Union[str, Path] = config.PECHAS_PATH):
        self.output_dir = Path(output_path)
        self._opf_path = None

        self.save_base()
        self.save_layers()
        self.save_index()
        self.save_meta()
        self.save_assets()
        return self.opf_path

    def remove(self):
        self.storage.remove_dir_with_path(name=self.pecha_path)


class OpenPechaBareGitRepo(OpenPecha):
    """
    Class to represent opf pecha in a bare git repo on the file-system.
    """

    def __init__(
        self,
        pecha_id: str = None,
        path: str = None,
        revision: str = "HEAD",
        repo=None,
        **kwargs,
    ):
        super().__init__(pecha_id=pecha_id, **kwargs)
        self.rev = revision
        if repo is not None:
            self.repo = repo
        else:
            self.repo = Repo(path)

    def read_file_content(self, oppath):
        return self.repo.git.show(f"{self.rev}:{self._pecha_id}.opf/" + oppath)

    def read_file_content_yml(self, oppath):
        ymlstr = None
        try:
            ymlstr = self.repo.git.show(f"{self.rev}:{self._pecha_id}.opf/" + oppath)
        except:
            return None
        return load_yaml_str(ymlstr)

    def _list_paths(self):
        """
        Getting all the files in the bare repo
        """
        files = self.repo.git.ls_tree(r=self.rev).split("\n")
        # removing the xxx.opf at the beginning
        files = [file.split("\t")[-1] for file in files]
        files = [
            file[len(self._pecha_id) + 5 :]
            for file in files
            if file.startswith(self.lname + ".")
            and (file.endswith(".txt") or file.endswith(".yml"))
        ]
        return files

    def _read_components(self):
        """
        get all bases and layers
        """
        paths = self._list_paths()
        res = {}

        for f in sorted(paths):
            path = f.split("/")
            if len(path) > 1:
                basename = path[-2]
                layername = Path(path[-1]).stem
                if basename not in res:
                    res[basename] = []
                res[basename].append(layername)
        return res

    def read_base_file(self, base_name: str) -> str:
        return self.read_file_content("base/" + base_name + ".txt")

    def read_layers_file(
        self, base_name: str, layer_name: LayerEnum
    ) -> Union[Dict, None]:
        return self.read_file_content_yml(
            "layers/" + base_name + "/" + layer_name + ".yml"
        )

    def read_meta_file(self) -> Dict:
        return self.read_file_content_yml("meta.yml")

    def read_index_file(self) -> Dict:
        return self.read_file_content_yml("index.yml")
