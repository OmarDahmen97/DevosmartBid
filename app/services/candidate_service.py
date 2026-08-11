# file: app/services/candidate_service.py

import re
from typing import List, Dict, Any, Optional
from bson import ObjectId
from pymongo.collection import Collection


class CandidateService:
    def __init__(self, merged_collection: Collection):
        """
        Receives the pre-initialized MongoDB collection 'merged_candidates'.
        """
        self.collection = merged_collection

    def _format_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Converts MongoDB ObjectIds to strings for JSON serialization."""
        if not doc:
            return doc
        if "_id" in doc and isinstance(doc["_id"], ObjectId):
            doc["_id"] = str(doc["_id"])
        if "candidate_id" in doc and isinstance(doc["candidate_id"], ObjectId):
            doc["candidate_id"] = str(doc["candidate_id"])
        return doc

    def build_advanced_query(
        self,
        skills: Optional[List[str]] = None,
        skills_match_all: bool = False,
        countries: Optional[List[str]] = None,
        company: Optional[str] = None,
        job_title: Optional[str] = None,
        certifications: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        degree: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Dynamically constructs a multi-criteria and multi-section MongoDB query
        strictly aligned with the candidate JSON schema.
        """
        conditions = []

        # Skills search across 'skills', 'experience.technologies', 'expertise_areas', and 'functional_skills'
        if skills:
            skills_conditions = []
            for s in skills:
                if not s or not s.strip():
                    continue
                pattern = f"^{s.strip()}$"
                skills_conditions.append({
                    "$or": [
                        {"skills": {"$regex": pattern, "$options": "i"}},
                        {"experience.technologies": {"$regex": pattern, "$options": "i"}},
                        {"expertise_areas.description": {"$regex": s.strip(), "$options": "i"}},
                        {"functional_skills.description": {"$regex": s.strip(), "$options": "i"}}
                    ]
                })
            
            if skills_conditions:
                if skills_match_all:
                    conditions.append({"$and": skills_conditions})
                else:
                    conditions.append({"$or": skills_conditions})

        # Countries search on 'countries_worked'
        if countries:
            country_conditions = [
                {"countries_worked": {"$regex": f"^{c.strip()}$", "$options": "i"}}
                for c in countries if c and c.strip()
            ]
            if country_conditions:
                conditions.append({"$or": country_conditions})

        # Experience -> Company
        if company and company.strip():
            conditions.append({
                "experience.company": {"$regex": company.strip(), "$options": "i"}
            })

        # Experience -> Title
        if job_title and job_title.strip():
            conditions.append({
                "experience.title": {"$regex": job_title.strip(), "$options": "i"}
            })

        # Certifications
        if certifications:
            cert_conditions = [
                {"certifications": {"$regex": f"^{cert.strip()}$", "$options": "i"}}
                for cert in certifications if cert and cert.strip()
            ]
            if cert_conditions:
                conditions.append({"$or": cert_conditions})

        # Languages (matching 'languages.language' in array of objects)
        if languages:
            lang_conditions = [
                {"languages.language": {"$regex": f"^{lang.strip()}$", "$options": "i"}}
                for lang in languages if lang and lang.strip()
            ]
            if lang_conditions:
                conditions.append({"$or": lang_conditions})

        # Education -> Degree
        if degree and degree.strip():
            conditions.append({
                "education.degree": {"$regex": degree.strip(), "$options": "i"}
            })

        if not conditions:
            return {}

        return {"$and": conditions} if len(conditions) > 1 else conditions[0]

    def filter_candidates(
        self,
        filters: Dict[str, Any],
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Executes search query returning only candidate IDs and names for performance optimization.
        """
        query = self.build_advanced_query(**filters)
        skip = (page - 1) * limit

        projection = {
            "_id": 1,
            "candidate_id": 1,
            "name": 1,
            "email": 1
        }

        cursor = self.collection.find(query, projection).skip(skip).limit(limit)
        results = [self._format_document(doc) for doc in cursor]
        total_count = self.collection.count_documents(query)

        return {
            "page": page,
            "limit": limit,
            "total": total_count,
            "total_pages": (total_count + limit - 1) // limit if limit > 0 else 1,
            "data": results,
        }

    def get_candidate_by_id(self, candidate_id_str: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the complete candidate document matching candidate_id_str against
        both '_id' and 'candidate_id', handling both ObjectId and String stored types.
        """
        if not candidate_id_str:
            return None

        clean_id = candidate_id_str.strip()

        or_conditions = [
            {"candidate_id": clean_id},
            {"_id": clean_id}
        ]

        if ObjectId.is_valid(clean_id):
            obj_id = ObjectId(clean_id)
            or_conditions.append({"candidate_id": obj_id})
            or_conditions.append({"_id": obj_id})

        doc = self.collection.find_one({"$or": or_conditions})

        return self._format_document(doc) if doc else None

    def get_distinct_skills(self) -> List[str]:
        """
        Returns a sorted, unique list of all skills across 'skills' and 'experience.technologies'.
        """
        raw_skills = self.collection.distinct("skills")
        
        
        all_skills = set()
        for item in raw_skills :
            if isinstance(item, str) and item.strip():
                all_skills.add(item.strip())
        
        return sorted(list(all_skills), key=lambda s: s.lower())

    def get_distinct_countries(self) -> List[str]:
        """
        Returns a sorted, unique list of countries from 'countries_worked'.
        """
        countries = self.collection.distinct("countries_worked")
        
        all_countries = set()
        for c in countries:
            if isinstance(c, str) and c.strip():
                all_countries.add(c.strip().capitalize())
                
        return sorted(list(all_countries))

    def get_distinct_job_titles(self) -> List[str]:
        """
        Returns a sorted, unique list of job titles from 'experience.title'.
        """
        titles = self.collection.distinct("experience.title")
        
        all_titles = set()
        for t in titles:
            if isinstance(t, str) and t.strip():
                all_titles.add(t.strip())
                
        return sorted(list(all_titles))

    def get_distinct_companies(self) -> List[str]:
        """
        Returns a sorted, unique list of companies from 'experience.company'.
        """
        companies = self.collection.distinct("experience.company")
        
        all_companies = set()
        for c in companies:
            if isinstance(c, str) and c.strip():
                all_companies.add(c.strip())
                
        return sorted(list(all_companies))

    def get_distinct_languages(self) -> List[str]:
        """
        Returns a sorted, unique list of languages from 'languages.language'.
        """
        langs = self.collection.distinct("languages.language")
        return sorted([l.strip() for l in langs if isinstance(l, str) and l.strip()])

    def get_distinct_certifications(self) -> List[str]:
        """
        Returns a sorted, unique list of certifications from 'certifications'.
        """
        certs = self.collection.distinct("certifications")
        return sorted([c.strip() for c in certs if isinstance(c, str) and c.strip()])

    def get_distinct_degrees(self) -> List[str]:
        """
        Returns a sorted, unique list of degrees from 'education.degree'.
        """
        degrees = self.collection.distinct("education.degree")
        return sorted([d.strip() for d in degrees if isinstance(d, str) and d.strip()])

    def get_all_filter_options(self) -> Dict[str, Any]:
        """
        Returns all unique filter options in a single dictionary for front-end initialization.
        """
        return {
            "skills": self.get_distinct_skills(),
            "countries": self.get_distinct_countries(),
            "job_titles": self.get_distinct_job_titles(),
            "companies": self.get_distinct_companies(),
            "languages": self.get_distinct_languages(),
            "certifications": self.get_distinct_certifications(),
            "degrees": self.get_distinct_degrees()
        }

    def suggest_skills(self, prefix: str, limit: int = 10) -> List[str]:
        """
        Suggère des compétences dont le nom commence exactement par le préfixe saisi.
        """
        if not prefix or not prefix.strip():
            return []

        clean_prefix = prefix.strip()
        regex_pattern = f"^{re.escape(clean_prefix)}"

        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"skills": {"$regex": regex_pattern, "$options": "i"}},
                        {"experience.technologies": {"$regex": regex_pattern, "$options": "i"}}
                    ]
                }
            },
            {
                "$project": {
                    "combined_skills": {
                        "$concatArrays": [
                            {"$ifNull": ["$skills", []]},
                            {"$ifNull": ["$experience.technologies", []]}
                        ]
                    }
                }
            },
            {"$unwind": "$combined_skills"},
            {
                "$match": {
                    "combined_skills": {"$regex": regex_pattern, "$options": "i"}
                }
            },
            {"$group": {"_id": "$combined_skills"}},
            {"$limit": limit * 2}
        ]

        results = list(self.collection.aggregate(pipeline))
        unique_matches = {
            doc["_id"].strip() for doc in results 
            if isinstance(doc["_id"], str) and doc["_id"].strip()
        }

        return sorted(list(unique_matches), key=lambda s: s.lower())[:limit]

    def suggest_companies(self, prefix: str, limit: int = 10) -> List[str]:
        """
        Suggère des entreprises dont le nom commence exactement par le préfixe saisi.
        """
        if not prefix or not prefix.strip():
            return []

        clean_prefix = prefix.strip()
        regex_pattern = f"^{re.escape(clean_prefix)}"

        pipeline = [
            {"$match": {"experience.company": {"$regex": regex_pattern, "$options": "i"}}},
            {"$unwind": "$experience"},
            {"$match": {"experience.company": {"$regex": regex_pattern, "$options": "i"}}},
            {"$group": {"_id": "$experience.company"}},
            {"$limit": limit * 2}
        ]

        results = list(self.collection.aggregate(pipeline))
        unique_matches = {
            doc["_id"].strip() for doc in results 
            if isinstance(doc["_id"], str) and doc["_id"].strip()
        }

        return sorted(list(unique_matches), key=lambda c: c.lower())[:limit]

    def suggest_job_titles(self, prefix: str, limit: int = 10) -> List[str]:
        """
        Suggère des intitulés de postes dont le titre commence exactement par le préfixe saisi.
        """
        if not prefix or not prefix.strip():
            return []

        clean_prefix = prefix.strip()
        regex_pattern = f"^{re.escape(clean_prefix)}"

        pipeline = [
            {"$match": {"experience.title": {"$regex": regex_pattern, "$options": "i"}}},
            {"$unwind": "$experience"},
            {"$match": {"experience.title": {"$regex": regex_pattern, "$options": "i"}}},
            {"$group": {"_id": "$experience.title"}},
            {"$limit": limit * 2}
        ]

        results = list(self.collection.aggregate(pipeline))
        unique_matches = {
            doc["_id"].strip() for doc in results 
            if isinstance(doc["_id"], str) and doc["_id"].strip()
        }

        return sorted(list(unique_matches), key=lambda t: t.lower())[:limit]

    def suggest_countries(self, prefix: str, limit: int = 10) -> List[str]:
        """
        Suggère des pays qui commencent exactement par le préfixe saisi.
        """
        if not prefix or not prefix.strip():
            return []

        clean_prefix = prefix.strip()
        regex_pattern = f"^{re.escape(clean_prefix)}"

        pipeline = [
            {"$match": {"countries_worked": {"$regex": regex_pattern, "$options": "i"}}},
            {"$unwind": "$countries_worked"},
            {"$match": {"countries_worked": {"$regex": regex_pattern, "$options": "i"}}},
            {"$group": {"_id": "$countries_worked"}},
            {"$limit": limit * 2}
        ]

        results = list(self.collection.aggregate(pipeline))
        unique_matches = {
            doc["_id"].strip().capitalize() for doc in results 
            if isinstance(doc["_id"], str) and doc["_id"].strip()
        }

        return sorted(list(unique_matches), key=lambda c: c.lower())[:limit]