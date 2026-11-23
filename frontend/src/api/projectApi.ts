
import api from "./axios";

export interface Project {
  id: number;
  name: string;
  slug: string;
  description: string;
  status: "ACTIVE" | "ARCHIVED" | "CANCELLED";
  workspace_name: string;
  workspace_slug: string;
  role: "MANAGER" | "MEMBER" | null;
  workspace_role: "OWNER" | "ADMIN" | "DEVELOPER" | null;
  created_at: string;
}

export interface ProjectMember {
  user_id: number;
  username: string;
  email: string;
  role: "MANAGER" | "MEMBER";
  joined_at: string;
}

export interface ProjectUpdateData {
  name?: string;
  description?: string;
  status?: "ACTIVE" | "ARCHIVED" | "CANCELLED";
}
export interface ProjectInsights {
  health: "HEALTHY" | "NEEDS_ATTENTION" | "AT_RISK";
  health_evidence: Record<string, unknown>;
  total_tasks: number;
  done_tasks: number;
  incomplete_tasks: number;
  overdue_count: number;
  due_soon_count: number;
  bottleneck_count: number;
  stale_blocker_count: number;
  critical_path_length: number;
  workload: {
    disclaimer: string;
    workload: {
      user_id: number;
      username: string;
      email: string;
      active_task_count: number;
    }[];
  };
}

export interface ProjectBottlenecks {
  bottlenecks: {
    task_id: number;
    task_title: string;
    status: string;
    priority: string;
    due_date: string | null;
    downstream_count: number;
    evidence: Record<string, unknown>;
  }[];
  stale_blockers: {
    task_id: number;
    task_title: string;
    status: string;
    days_blocked: number;
    blocking_task_ids: number[];
    evidence: Record<string, unknown>;
  }[];
}

export interface ProjectCriticalPath {
  length: number;
  evidence: Record<string, unknown>;
  tasks: {
    id: number;
    title: string;
    status: string;
    priority: string;
    due_date: string | null;
  }[];
}

export interface ProjectRecommendation {
  type: string;
  severity: "HIGH" | "MEDIUM";
  message: string;
  evidence: Record<string, unknown>;
}

// Workspace project listing
export const getWorkspaceProjects = async (
  workspaceSlug: string
): Promise<Project[]> => {
  const response = await api.get<Project[]>(
    `/workspaces/${workspaceSlug}/projects/`
  );
  return response.data;
};

// Create a project
export const createProject = async (
  workspaceSlug: string,
  name: string,
  description: string
): Promise<Project> => {
  const response = await api.post<Project>(
    `/workspaces/${workspaceSlug}/projects/`,
    { name, description }
  );
  return response.data;
};

// Fetch project details
export const getProject = async (
  projectId: number
): Promise<Project> => {
  const response = await api.get<Project>(`/projects/${projectId}/`);
  return response.data;
};

// Update project information or status
export const updateProject = async (
  projectId: number,
  data: ProjectUpdateData
): Promise<Project> => {
  await api.patch(`/projects/${projectId}/`, data);

  // Fetch the complete project after updating it.
  return getProject(projectId);
};

// Fetch project members
export const getProjectMembers = async (
  projectId: number
): Promise<ProjectMember[]> => {
  const response = await api.get<ProjectMember[]>(
    `/projects/${projectId}/members/`
  );
  return response.data;
};

// Add a workspace member to a project
export const addProjectMember = async (
  projectId: number,
  email: string,
  role: "MANAGER" | "MEMBER"
): Promise<ProjectMember> => {
  const response = await api.post<ProjectMember>(
    `/projects/${projectId}/members/`,
    { email, role }
  );
  return response.data;
};

// Change a project member's role
export const updateProjectMemberRole = async (
  projectId: number,
  userId: number,
  role: "MANAGER" | "MEMBER"
): Promise<ProjectMember> => {
  const response = await api.patch<ProjectMember>(
    `/projects/${projectId}/members/${userId}/`,
    { role }
  );
  return response.data;
};

// Remove a project member
export const removeProjectMember = async (
  projectId: number,
  userId: number
): Promise<void> => {
  await api.delete(`/projects/${projectId}/members/${userId}/`);
};
export const getProjectInsights = async (
  projectId: number
): Promise<ProjectInsights> => {
  const response = await api.get<ProjectInsights>(
    `/projects/${projectId}/insights/`
  );
  return response.data;
};

export const getProjectBottlenecks = async (
  projectId: number
): Promise<ProjectBottlenecks> => {
  const response = await api.get<ProjectBottlenecks>(
    `/projects/${projectId}/insights/bottlenecks/`
  );
  return response.data;
};

export const getProjectCriticalPath = async (
  projectId: number
): Promise<ProjectCriticalPath> => {
  const response = await api.get<ProjectCriticalPath>(
    `/projects/${projectId}/insights/critical-path/`
  );
  return response.data;
};

export const getProjectRecommendations = async (
  projectId: number
): Promise<ProjectRecommendation[]> => {
  const response = await api.get<{ recommendations: ProjectRecommendation[] }>(
    `/projects/${projectId}/recommendations/`
  );
  return response.data.recommendations;
};
export const deleteProject = async (projectId: number): Promise<void> => {
  await api.delete(`/projects/${projectId}/`);
};
