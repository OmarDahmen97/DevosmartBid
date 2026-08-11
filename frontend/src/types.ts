export type UploadResultItem = {
  filename: string;
  candidate_id: string;
  name: string | null;
  email: string | null;
  status: "new_candidate" | "new_version" | "duplicate";
  version: number;
  experience_count_after_merge: number;
};

export type UploadErrorItem = {
  filename: string;
  error: string;
};

export type UploadResponse = {
  results: (UploadResultItem | UploadErrorItem)[];
};

export type MatchCandidate = {
  candidate_id: string;
  name: string;
  email: string | null;
  avg_score: number;
};

export type MatchResponse = {
  candidates: MatchCandidate[];
};

export type CandidateSummary = {
  candidate_id: string;
  name: string;
  email: string | null;
};

export type AdvancedSearchResponse = {
  data: CandidateSummary[];
  page: number;
  limit: number;
  total: number;
  total_pages: number;
};

export type SuggestResponse = {
  suggestions: string[];
};

export type ExperienceItem = {
  experience_index: number;
  item: Record<string, unknown>;
  score: number;
  auto_selected: boolean;
};

export type ProjectItem = {
  project_index: number;
  item: Record<string, unknown>;
  score: number;
  auto_selected: boolean;
};

export type RankedResponse = {
  experiences: ExperienceItem[];
  projects: ProjectItem[];
};

export type GeneratedExperience = {
  title: string;
  company: string;
  dates: string;
  description: string;
  responsibilities: string[];
  _adapted?: boolean;
};

export type GeneratedProject = {
  name: string;
  description: string;
  _adapted?: boolean;
};

export type GeneratedContent = {
  summary: string;
  skills: string[];
  expertise_areas: string[];
  functional_skills: string[];
  education: string[];
  certifications: string[];
  languages: string[];
  countries_worked: string[];
  professional_affiliations: string[];
  experience: GeneratedExperience[];
  projects: GeneratedProject[];
};

export type GenerationResultItem = {
  candidate_id: string;
  name: string;
  generated_content: GeneratedContent;
};

export type GenerationResponse = {
  status: string;
  message: string;
  results: GenerationResultItem[];
};

export type CandidateDetail = Record<string, unknown>;

export type SelectionEntry = {
  candidate_id: string;
  name: string;
  email: string | null;
  source: "matching" | "search";
};

export type CandidateSelection = SelectionEntry & {
  selected_experience_indices: Set<number>;
  selected_project_indices: Set<number>;
};

export type Step = "upload" | "matching" | "review" | "generation";

export type Candidate = {
  id: string;
  name: string;
  role: string;
  match: number;
  country: string;
  experience: string;
  skills: string[];
  languages: string[];
  summary: string;
  added: string;
  education: string[];
  projects: string[];
  certifications: string[];
  company: string;
};
