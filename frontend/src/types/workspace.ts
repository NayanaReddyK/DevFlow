
export type WorkspaceRole = "OWNER" | "ADMIN" | "DEVELOPER";

export interface Workspace {
  id: number;
  name: string;
  slug: string;
  role: WorkspaceRole | null;
  created_at: string;
}
