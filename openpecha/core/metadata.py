from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Union,List

from pydantic import AnyHttpUrl, BaseModel, Extra, validator

from . import ids
import re

class InitialCreationType(Enum):
    ocr = "ocr"
    ebook = "ebook"
    input = "input"
    tmx = "tmx"


class CopyrightStatus(Enum):
    UNKNOWN = "Unknown"
    COPYRIGHTED = "In copyright"
    PUBLIC_DOMAIN = "Public domain"


class Copyright(BaseModel):
    status: CopyrightStatus = CopyrightStatus.UNKNOWN
    notice: Optional[str] = ""
    info_url: Optional[str] = None

    class Config:
        extra = Extra.forbid

Copyright_copyrighted = Copyright(
    status=CopyrightStatus.COPYRIGHTED,
    notice="In copyright by the original author or editor",
    info_url="http://rightsstatements.org/vocab/InC/1.0/",
)

Copyright_unknown = Copyright(
    status=CopyrightStatus.UNKNOWN,
    notice="Copyright Undertermined",
    info_url="http://rightsstatements.org/vocab/UND/1.0/",
)

Copyright_public_domain = Copyright(
    status=CopyrightStatus.PUBLIC_DOMAIN,
    notice="Public domain",
    info_url="https://creativecommons.org/publicdomain/mark/1.0/",
)

class LicenseType(Enum):
    # based on https://creativecommons.org/licenses/

    CC0 = "CC0"
    PUBLIC_DOMAIN_MARK = "Public Domain Mark"
    CC_BY = "CC BY"
    CC_BY_SA = "CC BY-SA"
    CC_BY_ND = "CC BY-ND"
    CC_BY_NC = "CC BY-NC"
    CC_BY_NC_SA = "CC BY-NC-SA"
    CC_BY_NC_ND = "CC BY-NC-ND"
    
    UNDER_COPYRIGHT = "under copyright"


class PechaMetadata(BaseModel):
    id: str = None
    legacy_id: Optional[str] = None
    ocr_import_info: Optional[Dict] = None
    default_language: str = None
    source: str = None
    source_file: str = None
    initial_creation_type: InitialCreationType = None
    imported: datetime = None
    last_modified: datetime = None
    parser: AnyHttpUrl = None
    source_metadata: Optional[Dict] = None  # place to dump any metadata from the source
    statistics: Optional[Dict] = None
    quality: Optional[Dict] = None
    bases: Optional[Dict[str, Dict]] = {}
    copyright: Copyright = None
    license: LicenseType = None

    @validator("imported", pre=True, always=True)
    def set_imported_date(cls, v):
        return v or datetime.now()

    @validator("last_modified", pre=True, always=True)
    def set_last_modified_date(cls, v):
        return v or datetime.now()

    @validator("copyright", pre=True, always=True)
    def set_copyright_info(cls, v):
        return v or Copyright()

    def update_last_modified_date(self):
        self.last_modified = datetime.now()

    # class Config:
    #     extra = Extra.forbid


class InitialPechaMetadata(PechaMetadata):
    bases: Dict = {}

    @validator("id", pre=True, always=True)
    def set_id(cls, v):
        return v or ids.get_initial_pecha_id()


class OpenPechaMetadata(PechaMetadata):
    @validator("id", pre=True, always=True)
    def set_id(cls, v):
        return v or ids.get_open_pecha_id()


class DiplomaticPechaMetadata(PechaMetadata):
    @validator("id", pre=True, always=True)
    def set_id(cls, v):
        return v or ids.get_diplomatic_id()

class AlignmentMetadata(BaseModel):
    id:str
    title:str
    type: str
    pechas: List[str]
    alignment_to_base:Dict[str,str]
    source_metadata: Optional[Dict] = None

class InstanceMetadata(BaseModel):
    id: str
    title: List[str]
    colophon: str
    authors: List[str]
    bdrc_id: str
    location_info: dict
    diplomatic_id:Optional[List[str]]
    alignmnet_ids:Optional[List[str]]
    collection_ids:Optional[List[str]]

    @validator("diplomatic_id")
    def validate_diplonatic_id(cls,value):
        if not re.match(r"I.*",value):
            raise ValueError("Pecha Id is not Diplomatic")


class WorkMetadata(BaseModel):
    id: str
    title: str
    alternative_title: Optional[str]
    language: str
    bdrc_work_id: str
    authors: List[str]
    best_instance:Optional[InstanceMetadata]
    instances: Optional[List[InstanceMetadata]]


class CollectionMetadata:
    pass
