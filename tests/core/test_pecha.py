import shutil
import tempfile
from pathlib import Path

import pytest

from openpecha.core.annotations import Span
from openpecha.core.layer import Layer, LayerEnum
from openpecha.core.metadata import InitialCreationType, InitialPechaMetadata
from openpecha.core.pecha import OpenPecha, OpenPechaFS


@pytest.fixture(scope="module")
def opf_path():
    return "tests/data/pechas/P000100.opf"


@pytest.fixture(scope="module")
def test_pechas_path():
    return Path("tests/data/pechas")


def test_create_pecha():
    openpecha = OpenPechaFS(
        bases={"v001": "this is base"},
        layers={
            "v001": {
                LayerEnum.citation: Layer(
                    annotation_type=LayerEnum.citation, revision="00001", annotations={}
                )
            }
        },
        metadata=InitialPechaMetadata(initial_creation_type=InitialCreationType.ebook),
        path="",
    )
    assert openpecha.meta.id
    assert openpecha.get_base("v001")
    assert openpecha.get_layer("v001", LayerEnum.citation)

    with tempfile.TemporaryDirectory() as tmpdirname:
        openpecha.save(tmpdirname)


def test_load_openpecha(opf_path):
    pecha = OpenPechaFS(path=opf_path)
    assert pecha.meta.id
    assert pecha.index
    assert pecha.get_base("v001")
    assert pecha.get_layer("v001", LayerEnum.citation)
    assert pecha.components

    with tempfile.TemporaryDirectory() as tmpdirname:
        pecha.save(tmpdirname)


def test_save_layer(opf_path):
    pecha = OpenPechaFS(path=opf_path)
    layer_fn = pecha.save_layer(
        "v002",
        LayerEnum.citation,
        Layer(annotation_type=LayerEnum.citation, revision="00001", annotations={}),
    )
    assert layer_fn.is_file()
    shutil.rmtree(str(layer_fn.parent))


def test_create_empty_layer(opf_path):
    pecha = OpenPechaFS(path=opf_path)
    layer = pecha.get_layer("v001", LayerEnum("BookNumber"))
    assert layer.annotation_type == LayerEnum("BookNumber")
    assert layer.revision == "00001"
    assert layer.annotations == {}


def test_set_base():
    metadata = InitialPechaMetadata(initial_creation_type=InitialCreationType.input)
    pecha = OpenPecha(metadata=metadata)

    base_name = pecha.set_base("base content")

    assert pecha.bases[base_name] == "base content"


def test_set_base_metadata():
    metadata = InitialPechaMetadata(initial_creation_type=InitialCreationType.input)
    pecha = OpenPecha(metadata=metadata)
    base_metadata = {"id": "id", "title": "title"}

    base_name = pecha.set_base("base content", metadata=base_metadata)
    base_name_2 = pecha.set_base("base content", metadata=base_metadata)

    assert base_name in pecha.meta.bases
    assert pecha.meta.bases[base_name]["id"] == "id"
    assert pecha.meta.bases[base_name]["title"] == "title"
    assert pecha.meta.bases[base_name]["base_file"] == f"{base_name}.txt"
    assert pecha.meta.bases[base_name_2]["base_file"] == f"{base_name_2}.txt"


def test_set_layer():
    metadata = InitialPechaMetadata(initial_creation_type=InitialCreationType.input)
    pecha = OpenPecha(metadata=metadata)
    base_name = pecha.set_base("base content")
    layer = Layer(annotation_type=LayerEnum.citation)

    pecha.set_layer(base_name, layer)

    assert pecha.layers[base_name][LayerEnum.citation].id == layer.id


def get_sub_string(string, span):
    return string[span.start : span.end + 1]  # noqa E203


def test_span_info_with_layers(test_pechas_path):
    opf_path = test_pechas_path / "span_info.opf"
    pecha = OpenPechaFS(path=opf_path)

    span_info = pecha.get_span_info(
        base_name="0001",
        span=Span(start=16, end=33),
        layers=[LayerEnum.citation, LayerEnum.tsawa],
    )

    assert (
        get_sub_string(span_info.text, span_info.layers[LayerEnum.citation][0].span)
        == "cc"
    )

    assert (
        get_sub_string(span_info.text, span_info.layers[LayerEnum.tsawa][0].span)
        == "rrrr\nrrrr"
    )


def test_span_info_with_all_layers(test_pechas_path):
    opf_path = test_pechas_path / "span_info.opf"
    pecha = OpenPechaFS(path=opf_path)

    span_info = pecha.get_span_info(
        base_name="0001",
        span=Span(start=16, end=33),
    )

    assert (
        get_sub_string(span_info.text, span_info.layers[LayerEnum.citation][0].span)
        == "cc"
    )

    assert (
        get_sub_string(span_info.text, span_info.layers[LayerEnum.tsawa][0].span)
        == "rrrr\nrrrr"
    )

    assert (
        get_sub_string(span_info.text, span_info.layers[LayerEnum.yigchung][0].span)
        == "yy"
    )


def test_span_info_without_layers(test_pechas_path):
    opf_path = test_pechas_path / "span_info.opf"
    pecha = OpenPechaFS(path=opf_path)

    span_info = pecha.get_span_info(
        base_name="0001",
        span=Span(start=1, end=10),
        layers=[LayerEnum.citation, LayerEnum.tsawa, LayerEnum.yigchung],
    )

    assert not span_info.layers


@pytest.mark.skip(reason="external api call")
def test_download_pecha():
    pecha = OpenPechaFS(pecha_id="P000108")

    assert pecha.opf_path.is_dir()

    shutil.rmtree(str(pecha.opf_path.parent))

    assert not pecha.opf_path.is_dir()


def test_multi_create_pecha():
    metadata = InitialPechaMetadata(initial_creation_type=InitialCreationType.input)
    pecha_01 = OpenPechaFS(metadata=metadata, path="")
    pecha_01_base_name = pecha_01.set_base("pecha_01 base content")

    assert pecha_01.bases[pecha_01_base_name] == "pecha_01 base content"

    pecha_02 = OpenPechaFS(metadata=metadata, path="")
    pecha_02_base_name = pecha_02.set_base("pecha_02 base content")

    assert len(pecha_02.bases) == 1
    assert pecha_02.bases[pecha_02_base_name] == "pecha_02 base content"


def test_pecha_base_names_list(opf_path):
    pecha = OpenPechaFS(path=opf_path)
    assert pecha.base_names_list == ["v001"]

@pytest.mark.skip(reason="Requires Github connection")
def test_pecha_github_publish(tmp_path):
    from openpecha.core.pecha import OpenPechaGitRepo
    metadata = InitialPechaMetadata(initial_creation_type=InitialCreationType.input)
    output_path = tmp_path / "pechas"
    pecha = OpenPechaGitRepo(metadata=metadata)
    pecha.set_base("base content")
    pecha.save(output_path=output_path)

    assert pecha.pecha_path.is_dir()

    pecha.publish()

    print(pecha.pecha_path)


def test_opf_path_OpenPechaGitRepo():
    from openpecha.core.pecha import OpenPechaGitRepo
    from openpecha import config
    import os 
    os.environ["OPENPECHA_DATA_GITHUB_ORG"] = "OpenPecha-Data"
    os.environ["GITHUB_TOKEN"] = "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"
    os.environ["GITHUB_USERNAME"] = "gangagyatso4364"
    pecha_id = "P000108"
    opf = OpenPechaGitRepo(pecha_id=pecha_id)
    expected_opf_path = config.PECHAS_PATH / pecha_id/ f"{pecha_id}.opf"
    assert opf.opf_path == expected_opf_path