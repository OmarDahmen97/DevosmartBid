
def diff_projects(old_projects: list[dict], new_projects: list[dict]) -> dict:
    old_by_name = {p["name"].lower(): p for p in old_projects}
    new_by_name = {p["name"].lower(): p for p in new_projects}

    added_keys = new_by_name.keys() - old_by_name.keys()
    removed_keys = old_by_name.keys() - new_by_name.keys()
    common_keys = old_by_name.keys() & new_by_name.keys()

    modified = []
    for key in common_keys:
        old_p, new_p = old_by_name[key], new_by_name[key]
        changed_fields = {}
        for field in ("description", "technologies"):
            if old_p.get(field) != new_p.get(field):
                changed_fields[field] = {"old": old_p.get(field), "new": new_p.get(field)}
        if changed_fields:
            modified.append({"name": new_p["name"], "changes": changed_fields})

    return {
        "added": sorted(new_by_name[k]["name"] for k in added_keys),
        "removed": sorted(old_by_name[k]["name"] for k in removed_keys),
        "modified": modified,
    }


def diff_experience(old_exp: list[dict], new_exp: list[dict]) -> dict:
    old_by_title = {e["title"].lower(): e for e in old_exp}
    new_by_title = {e["title"].lower(): e for e in new_exp}

    added_keys = new_by_title.keys() - old_by_title.keys()
    removed_keys = old_by_title.keys() - new_by_title.keys()
    common_keys = old_by_title.keys() & new_by_title.keys()

    modified = []
    for key in common_keys:
        old_e, new_e = old_by_title[key], new_by_title[key]
        changed_fields = {}
        for field in ("company", "dates", "description", "responsibilities"):
            if old_e.get(field) != new_e.get(field):
                changed_fields[field] = {"old": old_e.get(field), "new": new_e.get(field)}
        if changed_fields:
            modified.append({"title": new_e["title"], "changes": changed_fields})

    return {
        "added": sorted(new_by_title[k]["title"] for k in added_keys),
        "removed": sorted(old_by_title[k]["title"] for k in removed_keys),
        "modified": modified,
    }


def diff_cv_versions(old: dict, new: dict) -> dict:
    def to_lower_map(items):
        return {item.lower(): item for item in items}

    def diff_added(old_items, new_items):
        old_map, new_map = to_lower_map(old_items), to_lower_map(new_items)
        return sorted(new_map[k] for k in new_map.keys() - old_map.keys())

    def diff_removed(old_items, new_items):
        old_map, new_map = to_lower_map(old_items), to_lower_map(new_items)
        return sorted(old_map[k] for k in old_map.keys() - new_map.keys())

    old_skills = old.get("skills", [])
    new_skills = new.get("skills", [])
    old_certs = [c["name"] for c in old.get("certifications", [])]
    new_certs = [c["name"] for c in new.get("certifications", [])]

    return {
        "skills_added": diff_added(old_skills, new_skills),
        "skills_removed": diff_removed(old_skills, new_skills),
        "certifications_added": diff_added(old_certs, new_certs),
        "experience_diff": diff_experience(old.get("experience", []), new.get("experience", [])),
        "projects_diff": diff_projects(old.get("projects", []), new.get("projects", [])),
    }