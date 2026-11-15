
import api from "./axios";

export interface Project {
  id: number;
  name: string;
  slug: string;
  description: string;
  status: "ACTIVE" | "ARCHIVED" | "CANCELLED";
  workspace_name: string;
  role: "MANAGER" | "MEMBER" | null;
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
