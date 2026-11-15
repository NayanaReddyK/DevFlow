
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function DashboardPage() {
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error("Logout failed:", error);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-slate-800 px-8 py-5">
        <h1 className="text-2xl font-bold">DevFlow</h1>

        <button
          onClick={handleLogout}
          className="rounded-lg bg-slate-800 px-4 py-2 text-sm transition hover:bg-slate-700"
        >
          Logout
        </button>
      </header>

      {/* Dashboard content */}
      <section className="mx-auto max-w-6xl px-8 py-12">
        <h2 className="text-3xl font-bold">
          Welcome, {user?.first_name || user?.username}!
        </h2>

        <p className="mt-2 text-slate-400">
          Manage your engineering projects and workflows.
        </p>

        {/* Dashboard cards */}
        <div className="mt-10 grid gap-6 md:grid-cols-3">

          {/* Workspaces */}
          <Link
            to="/workspaces"
            className="rounded-xl border border-slate-800 bg-slate-900 p-6 transition hover:border-blue-500 hover:bg-slate-800"
          >
            <h3 className="text-lg font-semibold">Workspaces</h3>

            <p className="mt-2 text-sm text-slate-400">
              Manage your teams and workspaces.
            </p>

            <p className="mt-5 text-sm font-medium text-blue-400">
              Explore workspaces →
            </p>
          </Link>

          {/* Projects */}
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <h3 className="text-lg font-semibold">Projects</h3>

            <p className="mt-2 text-sm text-slate-400">
              Your projects will appear here.
            </p>
          </div>

          {/* Tasks */}
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <h3 className="text-lg font-semibold">My Tasks</h3>

            <p className="mt-2 text-sm text-slate-400">
              Your assigned tasks will appear here.
            </p>
          </div>

        </div>
      </section>
    </main>
  );
}
