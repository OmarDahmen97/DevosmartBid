from pydantic import BaseModel
from typing import Optional
from pydantic import field_validator

class Education(BaseModel):
    degree: Optional[str] = None  
    field_of_study: Optional[str] = None  
    institution: Optional[str] = None
    years: Optional[str] = None

    @field_validator("years", mode="before")
    @classmethod
    def coerce_years_to_str(cls, v):
        return str(v) if v is not None else None
    
class ExpertiseArea(BaseModel):
    category: Optional[str] = None
    description: Optional[str] = None     

class Responsibility(BaseModel):
    category: str
    description: Optional[str]

class Experience(BaseModel):
    title: str
    company: Optional[str] = None
    dates: Optional[str] = None
    description: Optional[str] = None
    responsibilities: list[Responsibility] = []
    deliverables: list[str] = []
    technologies: list[str] = []

    @field_validator("responsibilities", mode="before")
    @classmethod
    def normalize_responsibilities(cls, v):
        if v is None:
            return []
        result = []
        for r in v:
            if isinstance(r, str):
                result.append({"category": r, "description": None})
            else:
                result.append(r)
        return result

    @field_validator("deliverables", "technologies", mode="before")
    @classmethod
    def null_to_empty_list(cls, v):
        return v if v is not None else []

class Project(BaseModel):
    name: str
    description: Optional[str] = None
    technologies: list[str] = []

    @field_validator("technologies", mode="before")
    @classmethod
    def null_to_empty_list(cls, v):
        return v if v is not None else []

class Language(BaseModel):
    language: str
    level: Optional[str]

class Certification(BaseModel):
    name: str
    issuer: Optional[str] = None
    year: Optional[str] = None
    

class CVSchema(BaseModel):
    name: str
    summary: Optional[str] = None
    expertise_areas: list[ExpertiseArea] = []
    functional_skills: list[ExpertiseArea] = []
    countries_worked: list[str] = []
    professional_affiliations: list[str] = []
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    skills: list[str] = []
    education: list[Education] = []
    experience: list[Experience] = []
    projects: list[Project] = []
    certifications: list[Certification] = []
    languages: list[Language] = []

    @field_validator("skills", "education", "experience", "projects",
                      "expertise_areas", "functional_skills", "countries_worked",
                      "professional_affiliations", mode="before")
    @classmethod
    def null_to_empty_list(cls, v):
        return v if v is not None else []
    
    @field_validator("certifications", mode="before")
    @classmethod
    def normalize_certifications(cls, v):
        if v is None:
            return []
        result = []
        for c in v:
            if isinstance(c, str):
                result.append({"name": c, "issuer": None, "year": None})
            else:
                result.append(c)
        return result

    @field_validator("languages", mode="before")
    @classmethod
    def normalize_languages(cls, v):
        if v is None:
            return []
        result = []
        for lang in v:
            if isinstance(lang, str):
                result.append({"language": lang, "level": None})
            else:
                result.append(lang)
        return result