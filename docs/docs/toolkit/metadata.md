# Pecha Metadata

## Create Metadata for a Pecha

Since, OpenPecha as has three types of pecha, we have metadata classes to create metadata for each type of pecha. Here is the list of pecha types with it's associated metadata class.

Pecha Type | ID format | Metadata Class | Note
---|---|---|---
Work | W######## | `openpecha.core.metadata.WorkMetadata` | 
Initial | I######## | `openpecha.core.metadata.InitialPechaMetadata` | 
Diplomatic | D######## | `openpecha.core.metadata.DiplomaticPechaMetadata` | 
Open | O######## | `openpecha.core.metadata.OpenPechaMetadata` | 
Alignment | A######## | `openpecha.core.metadata.AlignmentMetadata` | 
Collection | C######## | `openpecha.core.metadata.CollectionMetadata` | 

here is an example to create metadata for *Initial Pecha* type

```python
{!../../docs_src/developer/metadata/create_metadata_tutorial001.py!}
```

!!! attention

    Only the `initial_creation_type` attribute is required, rest of the attributes are optional.

!!! attention

    No need to assign pecha id when creating metadata, the metadata class will automatically create id with correct id prefix for a particular pecha type.

## Examples

all developers should follow schema for `source_metadata` and `base` as in given examples

### Initial Pecha Metadata

```yaml
id: I7E1A43F2
source: https://library.bdrc.io
source_file: null
initial_creation_type: ocr
imported: '2020-03-28T12:12:38+00:00'
last_modified: '2022-06-08T11:28:52.590761+00:00'
parser: https://github.com/OpenPecha-dev/openpecha-toolkit/blob/231bba39dd1ba393320de82d4d08a604aabe80fc/openpecha/formatters/google_orc.py
ocr_word_median_confidence_index: 0.9
source_metadata:
    id: bdr:W3CN4314
    title: ཚད་མ་རིགས་པའི་གཏེར་གྱི་རྩ་བ།
    author: ''
    access: http://purl.bdrc.io/admindata/AccessOpen
    restrictedInChina: false
base:
    529C:
      source_metadata:
          image_group_id: I3CN8548
          title: ''
          total_pages: 62
      order: 1
      base_file: 529C.txt
      ocr_word_median_confidence_index: 0.9
```

## Adding Copyright and License

here is an example to add copyright and license in pecha's metadata

```python
{!../../docs_src/developer/metadata/add_copyright_and_license.py!}
```

### Copyright Status

OpenPecha provides three Copyright Status:

- `CopyrightStatus.UNKNOWN`, use if the Copyright of the pecha is unknown.
- `CopyrightStatus.COPYRIGHTED`, use if the pecha source is Copyright restricted.
- `CopyRightStatus.PUBLIC_DOMAIN`, use if the pecha source is in [Public Domain](https://wiki.creativecommons.org/wiki/Public_domain).


### Licenses

OpenPecha relies on [Creative Common Licenses](https://creativecommons.org/licenses/) for licensing any pecha on OpenPecha Repository,

We can access Creative Common Licenses through `LicenseType` enum.
