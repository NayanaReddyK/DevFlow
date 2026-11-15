
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getWorkspaces, createWorkspace } from "../api/workspaceApi";
import type { Workspace } from "../types/workspace";

export default function WorkspacesPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const fetchWorkspaces = async () => {
    try {
      setError("");
      const data = await getWorkspaces();
      setWorkspaces(data);
    } catch {
      setError("Unable to load workspaces.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const handleCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!name.trim()) return;

    try {
      setCreating(true);
      setError("");

      const newWorkspace = await createWorkspace(name.trim());

      setWorkspaces((previous) => [
        newWorkspace,
        ...previous,
      ]);

      setName("");
    } catch {
      setError("Unable to create workspace. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 px-8 py-5">
        <Link to="/dashboard" className="text-2xl font-bold">
          DevFlow
        </Link>
      </header>

      <section className="mx-auto max-w-6xl px-8 py-12">
        <div className="mb-10">
          <h1 className="text-3xl font-bold">Workspaces</h1>
          <p className="mt-2 text-slate-400">
            Organize your teams and engineering projects.
          </p>
        </div>

        <form
          onSubmit={handleCreate}
          className="mb-10 flex flex-col gap-3 sm:flex-row"
        >
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Enter workspace name"
            required
            className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none focus:border-blue-500"
          />

          <button
            type="submit"
            disabled={creating || !name.trim()}
            className="rounded-lg bg-blue-600 px-6 py-3 font-semibold hover:bg-blue-500 disabled:opacity-50"
          >
            {creating ? "Creating..." : "Create workspace"}
          </button>
        </form>

        {error && (
          <p role="alert" className="mb-6 text-red-400">
            {error}
          </p>
        )}

        {loading ? (
          <p className="text-slate-400">Loading workspaces...</p>
        ) : workspaces.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-700 p-12 text-center">
            <h2 className="text-xl font-semibold">
              No workspaces yet
            </h2>
            <p className="mt-2 text-slate-400">
              Create your first workspace to get started.
            </p>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {workspaces.map((workspace) => (
              
        <Link
            key={workspace.id}
            to={`/workspaces/${workspace.slug}`}
            className="block rounded-xl border border-slate-800 bg-slate-900 p-6 transition hover:border-blue-500 hover:bg-slate-800"
        >
            <h2 className="text-xl font-semibold">
            {workspace.name}
            </h2>

            <p className="mt-2 text-sm text-slate-400">
            Role: {workspace.role ?? "Member"}
            </p>

            <p className="mt-1 text-xs text-slate-500">
            Created:{" "}
            {new Date(workspace.created_at).toLocaleDateString()}
            </p>

            <p className="mt-5 text-sm text-blue-400">
            Open workspace →
            </p>
        </Link>
))}
            
          </div>
        )}
      </section>
    </main>
  );
}
