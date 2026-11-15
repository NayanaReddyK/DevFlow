
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import KanbanBoard from "../components/kanban/KanbanBoard";
import {
  addProjectMember,
  getProject,
  getProjectMembers,
  removeProjectMember,
  updateProject,
  updateProjectMemberRole,
  type Project,
  type ProjectMember,
} from "../api/projectApi";

export default function ProjectDetailsPage() {
  const { projectId } = useParams<{ projectId: string }>();

  const [project, setProject] = useState<Project | null>(null);
  const [members, setMembers] = useState<ProjectMember[]>([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [addingMember, setAddingMember] = useState(false);

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Project editing form
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  // Add member form
  const [email, setEmail] = useState("");
  const [memberRole, setMemberRole] = useState<"MANAGER" | "MEMBER">(
    "MEMBER"
  );

  const numericProjectId = Number(projectId);

  const loadProjectData = useCallback(async () => {
    if (!projectId || !Number.isInteger(numericProjectId) || numericProjectId <= 0) {
      setError("Invalid project ID.");
      setLoading(false);
      return;
    }

    try {
      setError("");

      const [projectData, memberData] = await Promise.all([
        getProject(numericProjectId),
        getProjectMembers(numericProjectId),
      ]);

      setProject(projectData);
      setMembers(memberData);
      setName(projectData.name);
      setDescription(projectData.description || "");
    } catch {
      setError("Unable to load project details or members.");
    } finally {
      setLoading(false);
    }
  }, [projectId, numericProjectId]);

  useEffect(() => {
    loadProjectData();
  }, [loadProjectData]);

  // A null project role means the user has workspace-level access
  // rather than a ProjectMember record. Django still enforces permissions.
  const canManageProject =
    project?.role === null || project?.role === "MANAGER";

  const isCancelled = project?.status === "CANCELLED";
  const isArchived = project?.status === "ARCHIVED";

  const clearMessages = () => {
    setError("");
    setSuccess("");
  };

  // Save project name and description
  const handleSaveProject = async (
    event: React.FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();

    if (!project || !name.trim()) return;

    try {
      setSaving(true);
      clearMessages();

      const updatedProject = await updateProject(project.id, {
        name: name.trim(),
        description: description.trim(),
      });

      setProject(updatedProject);
      setSuccess("Project details updated successfully.");
    } catch {
      setError("Unable to update project. Check your permissions.");
    } finally {
      setSaving(false);
    }
  };

  // Archive or reactivate a project
  const handleStatusChange = async (
    newStatus: "ACTIVE" | "ARCHIVED"
  ) => {
    if (!project) return;

    const action = newStatus === "ARCHIVED" ? "archive" : "reactivate";

    const confirmed = window.confirm(
      `Are you sure you want to ${action} this project?`
    );

    if (!confirmed) return;

    try {
      clearMessages();

      const updatedProject = await updateProject(project.id, {
        status: newStatus,
      });

      setProject(updatedProject);
      setSuccess(
        newStatus === "ARCHIVED"
          ? "Project archived successfully."
          : "Project reactivated successfully."
      );
    } catch {
      setError("Unable to change project status. Check your permissions.");
    }
  };

  // Add project member
  const handleAddMember = async (
    event: React.FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();

    if (!project || !email.trim()) return;

    try {
      setAddingMember(true);
      clearMessages();

      await addProjectMember(
        project.id,
        email.trim(),
        memberRole
      );

      setEmail("");
      setMemberRole("MEMBER");
      setSuccess("Project member added successfully.");

      await loadProjectData();
    } catch {
      setError(
        "Unable to add member. They must already belong to this workspace, and you must have permission."
      );
    } finally {
      setAddingMember(false);
    }
  };

  // Change member role
  const handleRoleChange = async (
    userId: number,
    newRole: "MANAGER" | "MEMBER"
  ) => {
    if (!project) return;

    try {
      clearMessages();

      await updateProjectMemberRole(
        project.id,
        userId,
        newRole
      );

      setSuccess("Project member role updated successfully.");
      await loadProjectData();
    } catch {
      setError(
        "Unable to update this role. Only workspace Owners and Admins can assign Managers."
      );
      await loadProjectData();
    }
  };

  // Remove member
  const handleRemoveMember = async (member: ProjectMember) => {
    if (!project) return;

    const confirmed = window.confirm(
      `Remove ${member.username} from this project?`
    );

    if (!confirmed) return;

    try {
      clearMessages();

      await removeProjectMember(project.id, member.user_id);

      setSuccess("Project member removed successfully.");
      await loadProjectData();
    } catch {
      setError(
        "Unable to remove this member. The project creator cannot be removed."
      );
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 p-8 text-white">
        Loading project...
      </main>
    );
  }

  if (!project) {
    return (
      <main className="min-h-screen bg-slate-950 p-8 text-white">
        <p role="alert" className="text-red-400">
          {error || "Project not found."}
        </p>

        <Link
          to="/workspaces"
          className="mt-4 inline-block text-blue-400"
        >
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

      <section className="mx-auto max-w-6xl px-6 py-10">
        <Link
          to="/workspaces"
          className="text-sm text-blue-400 hover:text-blue-300"
        >
          ← Back to workspaces
        </Link>

        {/* Project header */}
        <div className="mt-8 flex flex-col justify-between gap-5 md:flex-row md:items-start">
          <div>
            <h1 className="text-3xl font-bold">{project.name}</h1>

            <p className="mt-2 text-slate-400">
              {project.description || "No description provided."}
            </p>

            <div className="mt-4 flex flex-wrap gap-3">
              <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-blue-300">
                {project.status}
              </span>

              <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">
                {project.role ?? "Workspace access"}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            {canManageProject && !isCancelled && (
              <>
                {isArchived ? (
                  <button
                    onClick={() => handleStatusChange("ACTIVE")}
                    className="rounded-lg bg-green-700 px-4 py-2 text-sm font-medium hover:bg-green-600"
                  >
                    Reactivate project
                  </button>
                ) : (
                  <button
                    onClick={() => handleStatusChange("ARCHIVED")}
                    className="rounded-lg border border-amber-700 px-4 py-2 text-sm text-amber-300 hover:bg-amber-950"
                  >
                    Archive project
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {isCancelled && (
          <div className="mt-6 rounded-lg border border-red-900 bg-red-950/30 p-4 text-sm text-red-300">
            This project has been cancelled and is read-only.
          </div>
        )}

        {isArchived && (
          <div className="mt-6 rounded-lg border border-amber-900 bg-amber-950/30 p-4 text-sm text-amber-300">
            This project is archived. You can reactivate it if you have permission.
          </div>
        )}

        {error && (
          <p role="alert" className="mt-6 rounded-lg bg-red-950/40 p-3 text-sm text-red-400">
            {error}
          </p>
        )}

        {success && (
          <p role="status" className="mt-6 rounded-lg bg-green-950/40 p-3 text-sm text-green-400">
            {success}
          </p>
        )}

        {/* Project information */}
        <section className="mt-10 rounded-xl border border-slate-800 bg-slate-900 p-6">
          <h2 className="text-xl font-semibold">Project Information</h2>

          <div className="mt-5 grid gap-5 text-sm sm:grid-cols-2">
            <div>
              <p className="text-slate-500">Project ID</p>
              <p className="mt-1">{project.id}</p>
            </div>

            <div>
              <p className="text-slate-500">Project slug</p>
              <p className="mt-1">{project.slug}</p>
            </div>

            <div>
              <p className="text-slate-500">Workspace</p>
              <p className="mt-1">{project.workspace_name}</p>
            </div>

            <div>
              <p className="text-slate-500">Created</p>
              <p className="mt-1">
                {new Date(project.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>
        </section>
      {/* Kanban Board */}
<section className="mt-10">
  <div className="mb-5">
    <h2 className="text-2xl font-semibold">Task Board</h2>
    <p className="mt-1 text-sm text-slate-400">
      Track and manage tasks across project stages.
    </p>
  </div>

  {isArchived || isCancelled ? (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-5 text-sm text-slate-400">
      The task board is read-only because this project is {project.status.toLowerCase()}.
    </div>
  ) : (
    <KanbanBoard 
      projectId={project.id} 
      members={members}
      />

  )}
</section>
        {/* Edit project */}
        {canManageProject && !isCancelled && (
          <section className="mt-8 rounded-xl border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-xl font-semibold">Project Settings</h2>

            <form onSubmit={handleSaveProject} className="mt-5 space-y-4">
              <div>
                <label className="mb-2 block text-sm text-slate-300">
                  Project name
                </label>

                <input
                  type="text"
                  required
                  maxLength={100}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  disabled={saving}
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white outline-none focus:border-blue-500 disabled:opacity-50"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm text-slate-300">
                  Description
                </label>

                <textarea
                  rows={4}
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  disabled={saving}
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white outline-none focus:border-blue-500 disabled:opacity-50"
                />
              </div>

              <button
                type="submit"
                disabled={saving || !name.trim()}
                className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold hover:bg-blue-500 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save changes"}
              </button>
            </form>
          </section>
        )}

        {/* Add project member */}
        {canManageProject && !isArchived && !isCancelled && (
          <section className="mt-8 rounded-xl border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-xl font-semibold">Add Project Member</h2>

            <p className="mt-2 text-sm text-slate-400">
              The user must already be a member of this workspace.
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
                placeholder="Enter workspace member's email"
                className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white outline-none focus:border-blue-500"
              />

              <select
                value={memberRole}
                onChange={(event) =>
                  setMemberRole(
                    event.target.value as "MANAGER" | "MEMBER"
                  )
                }
                className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white"
              >
                <option value="MEMBER">Member</option>
                <option value="MANAGER">Manager</option>
              </select>

              <button
                type="submit"
                disabled={addingMember || !email.trim()}
                className="rounded-lg bg-blue-600 px-6 py-3 font-semibold hover:bg-blue-500 disabled:opacity-50"
              >
                {addingMember ? "Adding..." : "Add member"}
              </button>
            </form>
          </section>
        )}

        {/* Project members */}
        <section className="mt-10">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold">Project Members</h2>
              <p className="mt-1 text-sm text-slate-400">
                {members.length} project member{members.length === 1 ? "" : "s"}
              </p>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-800">
            {members.length === 0 ? (
              <p className="bg-slate-900 p-6 text-slate-400">
                No project members found.
              </p>
            ) : (
              <div className="divide-y divide-slate-800">
                {members.map((member) => (
                  <div
                    key={member.user_id}
                    className="flex flex-col justify-between gap-4 bg-slate-900 p-5 md:flex-row md:items-center"
                  >
                    <div>
                      <h3 className="font-semibold">{member.username}</h3>

                      <p className="mt-1 text-sm text-slate-400">
                        {member.email}
                      </p>

                      <p className="mt-2 text-xs text-slate-500">
                        Joined{" "}
                        {new Date(member.joined_at).toLocaleDateString()}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-blue-300">
                        {member.role}
                      </span>

                      {canManageProject &&
                        !isArchived &&
                        !isCancelled && (
                          <>
                            <select
                              value={member.role}
                              onChange={(event) =>
                                handleRoleChange(
                                  member.user_id,
                                  event.target.value as "MANAGER" | "MEMBER"
                                )
                              }
                              aria-label={`Change role for ${member.username}`}
                              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                            >
                              <option value="MEMBER">Member</option>
                              <option value="MANAGER">Manager</option>
                            </select>

                            <button
                              onClick={() => handleRemoveMember(member)}
                              className="rounded-lg border border-red-900 px-3 py-2 text-sm text-red-400 hover:bg-red-950"
                            >
                              Remove
                            </button>
                          </>
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
