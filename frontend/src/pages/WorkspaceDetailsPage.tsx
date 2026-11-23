
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import {
  createProject,
  getWorkspaceProjects,
  type Project,
} from "../api/projectApi";
import {
  addWorkspaceMember,
  deleteWorkspace,
  getWorkspace,
  getWorkspaceMembers,
  removeWorkspaceMember,
  updateWorkspaceMemberRole,
  type WorkspaceMember,
} from "../api/workspaceApi";

import type { Workspace } from "../types/workspace";

export default function WorkspaceDetailsPage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [creatingProject, setCreatingProject] = useState(false);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"ADMIN" | "DEVELOPER">("DEVELOPER");

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [deletingWorkspace, setDeletingWorkspace] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadWorkspace = useCallback(async () => {
    if (!slug) return;

    try {
      const [workspaceData, memberData, projectData] = await Promise.all([
  getWorkspace(slug),
  getWorkspaceMembers(slug),
  getWorkspaceProjects(slug),
]);

setWorkspace(workspaceData);
setMembers(memberData);
setProjects(projectData);
      setError("");

      setWorkspace(workspaceData);
      setMembers(memberData);
    } catch {
      setError("Unable to load workspace details.");
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    // State updates happen when the asynchronous API requests resolve.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadWorkspace();
  }, [loadWorkspace]);

  const isOwner = workspace?.role === "OWNER";
  const canManageMembers =
    workspace?.role === "OWNER" || workspace?.role === "ADMIN";
  const handleCreateProject = async (
  event: React.FormEvent<HTMLFormElement>
) => {
  event.preventDefault();

  if (!slug || !projectName.trim()) return;

  try {
    setCreatingProject(true);
    setError("");
    setSuccess("");

    const newProject = await createProject(
      slug,
      projectName.trim(),
      projectDescription.trim()
    );

    setProjects((previous) => [newProject, ...previous]);

    setProjectName("");
    setProjectDescription("");

    setSuccess("Project created successfully.");
  } catch {
    setError("Unable to create project. Check your permissions and try again.");
  } finally {
    setCreatingProject(false);
  }
};
  
  const handleAddMember = async (
    event: React.FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();

    if (!slug || !email.trim()) return;

    try {
      setSubmitting(true);
      setError("");
      setSuccess("");

      await addWorkspaceMember(slug, email.trim(), role);

      setEmail("");
      setSuccess("Member added successfully.");

      await loadWorkspace();
    } catch {
      setError(
        "Unable to add member. Check the email and your workspace permissions."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleRoleChange = async (
    userId: number,
    newRole: "ADMIN" | "DEVELOPER"
  ) => {
    if (!slug) return;

    try {
      setError("");
      setSuccess("");

      await updateWorkspaceMemberRole(slug, userId, newRole);

      setSuccess("Member role updated successfully.");
      await loadWorkspace();
    } catch {
      setError("Unable to update this member's role.");
    }
  };

  const handleRemoveMember = async (member: WorkspaceMember) => {
    if (!slug) return;

    const confirmed = window.confirm(
      `Are you sure you want to remove ${member.username} from this workspace?`
    );

    if (!confirmed) return;

    try {
      setError("");
      setSuccess("");

      await removeWorkspaceMember(slug, member.user_id);

      setSuccess("Member removed successfully.");
      await loadWorkspace();
    } catch {
      setError("Unable to remove this member.");
    }
  };

  const handleDeleteWorkspace = async () => {
    if (!slug || !workspace || projects.length > 0) return;

    const confirmed = window.confirm(
      `Permanently delete workspace "${workspace.name}"? This cannot be undone.`
    );
    if (!confirmed) return;

    try {
      setDeletingWorkspace(true);
      setError("");
      setSuccess("");
      await deleteWorkspace(slug);
      navigate("/workspaces");
    } catch (deleteError: unknown) {
      const message = axios.isAxiosError<{ detail?: string }>(deleteError)
        ? deleteError.response?.data?.detail
        : undefined;
      setError(message ?? "Unable to delete this workspace.");
    } finally {
      setDeletingWorkspace(false);
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 p-8 text-white">
        Loading workspace...
      </main>
    );
  }

  if (!workspace) {
    return (
      <main className="min-h-screen bg-slate-950 p-8 text-white">
        <p role="alert" className="text-red-400">
          {error || "Workspace not found."}
        </p>

        <Link to="/workspaces" className="mt-4 inline-block text-blue-400">
          Back to workspaces
        </Link>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="flex items-center justify-between border-b border-slate-800 px-8 py-5">
        <Link to="/dashboard" className="text-2xl font-bold">
          DevFlow
        </Link>

        <Link
          to="/workspaces"
          className="text-sm text-blue-400 hover:text-blue-300"
        >
          All workspaces
        </Link>
      </header>

      <section className="mx-auto max-w-6xl px-8 py-12">
        <Link
          to="/workspaces"
          className="text-sm text-slate-400 hover:text-white"
        >
          ← Back to workspaces
        </Link>

        <div className="mt-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">{workspace.name}</h1>

            <div className="mt-3 flex flex-wrap gap-3 text-sm text-slate-400">
              <span>
                Your role:{" "}
                <span className="font-medium text-blue-400">
                  {workspace.role}
                </span>
              </span>

              <span>•</span>

              <span>{members.length} members</span>
            </div>
          </div>

          {isOwner && projects.length === 0 && (
            <button
              type="button"
              onClick={handleDeleteWorkspace}
              disabled={deletingWorkspace}
              className="rounded-lg border border-red-900 px-4 py-2 text-sm text-red-400 hover:bg-red-950 disabled:opacity-50"
            >
              {deletingWorkspace ? "Deleting..." : "Delete workspace"}
            </button>
          )}
        </div>

        {isOwner && projects.length > 0 && (
          <p className="mt-4 text-sm text-slate-500">
            Delete all projects before deleting this workspace.
          </p>
        )}

        {error && (
          <p role="alert" className="mt-6 text-red-400">
            {error}
          </p>
        )}

        {success && (
          <p role="status" className="mt-6 text-green-400">
            {success}
          </p>
        )}
        {/* Projects */}
<section className="mt-10">
  <div className="mb-5">
    <h2 className="text-xl font-semibold">Projects</h2>
    <p className="mt-1 text-sm text-slate-400">
      Projects belonging to this workspace.
    </p>
  </div>
   {(isOwner || workspace.role === "ADMIN") && (
  <form
    onSubmit={handleCreateProject}
    className="mb-6 rounded-xl border border-slate-800 bg-slate-900 p-6"
  >
    <h3 className="text-lg font-semibold">Create a project</h3>

    <div className="mt-4 space-y-4">
      <input
        type="text"
        required
        value={projectName}
        onChange={(event) => setProjectName(event.target.value)}
        placeholder="Project name"
        className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white outline-none focus:border-blue-500"
      />

      <textarea
        value={projectDescription}
        onChange={(event) => setProjectDescription(event.target.value)}
        placeholder="Project description (optional)"
        rows={3}
        className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white outline-none focus:border-blue-500"
      />

      <button
        type="submit"
        disabled={creatingProject || !projectName.trim()}
        className="rounded-lg bg-blue-600 px-5 py-3 font-semibold transition hover:bg-blue-500 disabled:opacity-50"
      >
        {creatingProject ? "Creating..." : "Create project"}
      </button>
    </div>
  </form>
)}
  {projects.length === 0 ? (
    <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center">
      <h3 className="font-semibold">No projects yet</h3>
      <p className="mt-2 text-sm text-slate-400">
        Projects created in this workspace will appear here.
      </p>
    </div>
  ) : (
    <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
      {projects.map((project) => (
        <Link
          key={project.id}
          to={`/projects/${project.id}`}
          className="rounded-xl border border-slate-800 bg-slate-900 p-5 transition hover:border-blue-500"
        >
          <h3 className="text-lg font-semibold">
            {project.name}
          </h3>

          <p className="mt-2 text-sm text-slate-400">
            {project.description || "No description provided."}
          </p>

          <div className="mt-5 flex items-center justify-between">
            <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-blue-300">
              {project.status}
            </span>

            <span className="text-xs text-slate-400">
              {project.role ?? "Workspace access"}
            </span>
          </div>

          <p className="mt-4 text-xs text-slate-500">
            Created:{" "}
            {new Date(project.created_at).toLocaleDateString()}
          </p>
        </Link>
      ))}
    </div>
  )}
</section>
        {/* Add member */}
        {canManageMembers && (
          <section className="mt-10 rounded-xl border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-xl font-semibold">Add a member</h2>

            <p className="mt-2 text-sm text-slate-400">
              Add an existing DevFlow user using their registered email.
            </p>

            <form
              onSubmit={handleAddMember}
              className="mt-5 flex flex-col gap-4 md:flex-row"
            >
              <input
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="Enter user's email"
                className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white outline-none focus:border-blue-500"
              />

              <select
                value={role}
                onChange={(event) =>
                  setRole(event.target.value as "ADMIN" | "DEVELOPER")
                }
                className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white"
              >
                <option value="DEVELOPER">Developer</option>

                {isOwner && (
                  <option value="ADMIN">Admin</option>
                )}
              </select>

              <button
                type="submit"
                disabled={submitting}
                className="rounded-lg bg-blue-600 px-6 py-3 font-semibold transition hover:bg-blue-500 disabled:opacity-50"
              >
                {submitting ? "Adding..." : "Add member"}
              </button>
            </form>
          </section>
        )}

        {/* Members list */}
        <section className="mt-10">
          <h2 className="text-xl font-semibold">Workspace members</h2>

          <div className="mt-5 overflow-hidden rounded-xl border border-slate-800">
            {members.length === 0 ? (
              <p className="p-6 text-slate-400">
                No members found.
              </p>
            ) : (
              <div className="divide-y divide-slate-800">
                {members.map((member) => (
                  <div
                    key={member.user_id}
                    className="flex flex-col justify-between gap-4 bg-slate-900 p-5 md:flex-row md:items-center"
                  >
                    <div>
                      <h3 className="font-semibold">
                        {member.username}
                      </h3>

                      <p className="mt-1 text-sm text-slate-400">
                        {member.email}
                      </p>

                      <p className="mt-2 text-xs text-slate-500">
                        Joined{" "}
                        {new Date(member.joined_at).toLocaleDateString()}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <span className="rounded-full bg-slate-800 px-3 py-1 text-xs font-medium text-blue-300">
                        {member.role}
                      </span>

                      {isOwner && member.role !== "OWNER" && (
                        <select
                          value={member.role}
                          onChange={(event) =>
                            handleRoleChange(
                              member.user_id,
                              event.target.value as "ADMIN" | "DEVELOPER"
                            )
                          }
                          aria-label={`Change role for ${member.username}`}
                          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                        >
                          <option value="DEVELOPER">Developer</option>
                          <option value="ADMIN">Admin</option>
                        </select>
                      )}

                      {canManageMembers && member.role !== "OWNER" && (
                        <button
                          onClick={() => handleRemoveMember(member)}
                          className="rounded-lg border border-red-900 px-3 py-2 text-sm text-red-400 transition hover:bg-red-950"
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </section>
    </main>
  );
}
