
import api from "./axios";
import type { Workspace } from "../types/workspace";

export interface WorkspaceMember {
  user_id: number;
  username: string;
  email: string;
  role: "OWNER" | "ADMIN" | "DEVELOPER";
  joined_at: string;
}

export interface WorkspaceInvitation {
  id: number;
  email: string;
  role: "ADMIN" | "DEVELOPER";
  created_at: string;
  expires_at: string;
  accepted_at: string | null;
}

export const getWorkspaces = async (): Promise<Workspace[]> => {
  const response = await api.get<Workspace[]>("/workspaces/");
  return response.data;
};

export const createWorkspace = async (
  name: string
): Promise<Workspace> => {
  const response = await api.post<Workspace>("/workspaces/", { name });
  return response.data;
};

export const getWorkspace = async (
  slug: string
): Promise<Workspace> => {
  const response = await api.get<Workspace>(`/workspaces/${slug}/`);
  return response.data;
};

export const getWorkspaceMembers = async (
  slug: string
): Promise<WorkspaceMember[]> => {
  const response = await api.get<WorkspaceMember[]>(
    `/workspaces/${slug}/members/`
  );
  return response.data;
};

export const addWorkspaceMember = async (
  slug: string,
  email: string,
  role: "ADMIN" | "DEVELOPER"
): Promise<WorkspaceMember> => {
  const response = await api.post<WorkspaceMember>(
    `/workspaces/${slug}/members/`,
    { email, role }
  );

  return response.data;
};

export const updateWorkspaceMemberRole = async (
  slug: string,
  userId: number,
  role: "ADMIN" | "DEVELOPER"
): Promise<WorkspaceMember> => {
  const response = await api.patch<WorkspaceMember>(
    `/workspaces/${slug}/members/${userId}/`,
    { role }
  );

  return response.data;
};

export const removeWorkspaceMember = async (
  slug: string,
  userId: number
): Promise<void> => {
  await api.delete(`/workspaces/${slug}/members/${userId}/`);
};

export const getWorkspaceInvitations = async (
  slug: string
): Promise<WorkspaceInvitation[]> => {
  const response = await api.get<WorkspaceInvitation[]>(
    `/workspaces/${slug}/invitations/`
  );

  return response.data;
};
export const deleteWorkspace = async (slug: string): Promise<void> => {
  await api.delete(`/workspaces/${slug}/`);
};