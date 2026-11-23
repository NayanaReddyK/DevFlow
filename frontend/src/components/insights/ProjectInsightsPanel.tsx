import { useEffect, useState } from "react";
import {
  getProjectBottlenecks,
  getProjectCriticalPath,
  getProjectInsights,
  getProjectRecommendations,
  type ProjectBottlenecks,
  type ProjectCriticalPath,
  type ProjectInsights,
  type ProjectRecommendation,
} from "../../api/projectApi";

interface ProjectInsightsPanelProps {
  projectId: number;
}

interface DashboardData {
  summary: ProjectInsights;
  findings: ProjectBottlenecks;
  criticalPath: ProjectCriticalPath;
  recommendations: ProjectRecommendation[];
}

const healthStyles: Record<ProjectInsights["health"], string> = {
  HEALTHY: "border-green-800 bg-green-950/40 text-green-300",
  NEEDS_ATTENTION: "border-amber-800 bg-amber-950/40 text-amber-300",
  AT_RISK: "border-red-800 bg-red-950/40 text-red-300",
};

function Evidence({ value }: { value: Record<string, unknown> }) {
  return (
    <details className="mt-2 text-xs text-slate-400">
      <summary className="cursor-pointer hover:text-slate-200">
        Show evidence
      </summary>
      <pre className="mt-2 overflow-x-auto rounded bg-slate-950 p-3">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}

export default function ProjectInsightsPanel({
  projectId,
}: ProjectInsightsPanelProps) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadInsights() {
      setLoading(true);
      setError("");

      try {
        const [summary, findings, criticalPath, recommendations] =
          await Promise.all([
            getProjectInsights(projectId),
            getProjectBottlenecks(projectId),
            getProjectCriticalPath(projectId),
            getProjectRecommendations(projectId),
          ]);

        if (!cancelled) {
          setData({ summary, findings, criticalPath, recommendations });
        }
      } catch {
        if (!cancelled) {
          setError("Unable to load project insights.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadInsights();

    return () => {
      cancelled = true;
    };
  }, [projectId]);

  if (loading) {
    return (
      <section className="mt-10 rounded-xl border border-slate-800 bg-slate-900 p-6">
        <p className="text-slate-400">Loading project insights...</p>
      </section>
    );
  }

  if (error || !data) {
    return (
      <section className="mt-10 rounded-xl border border-slate-800 bg-slate-900 p-6">
        <p role="alert" className="text-red-400">
          {error || "Project insights are unavailable."}
        </p>
      </section>
    );
  }

  const { summary, findings, criticalPath, recommendations } = data;

  return (
    <section className="mt-10 rounded-xl border border-slate-800 bg-slate-900 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">Workflow Insights</h2>
          <p className="mt-1 text-sm text-slate-400">
            Rule-based findings calculated from this project’s tasks.
          </p>
        </div>

        <span
          className={`rounded-full border px-3 py-1 text-sm ${healthStyles[summary.health]}`}
        >
          {summary.health.replaceAll("_", " ")}
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-400">
        Health is based on deterministic workflow rules, not a guaranteed prediction.
      </p>
      <Evidence value={summary.health_evidence} />

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Tasks", summary.total_tasks],
          ["Overdue", summary.overdue_count],
          ["Due soon", summary.due_soon_count],
          ["Bottlenecks", summary.bottleneck_count],
          ["Stale blockers", summary.stale_blocker_count],
          ["Critical path length", criticalPath.length],
        ].map(([label, value]) => (
          <div
            key={label}
            className="rounded-lg border border-slate-800 bg-slate-950 p-4"
          >
            <p className="text-sm text-slate-400">{label}</p>
            <p className="mt-1 text-2xl font-semibold">{value}</p>
          </div>
        ))}
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-2">
        <div>
          <h3 className="text-lg font-semibold">Bottlenecks</h3>
          {findings.bottlenecks.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">No bottlenecks found.</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {findings.bottlenecks.map((item) => (
                <li
                  key={item.task_id}
                  className="rounded-lg border border-slate-800 p-4"
                >
                  <p className="font-medium">{item.task_title}</p>
                  <p className="mt-1 text-sm text-slate-400">
                    Blocks {item.downstream_count} downstream task(s)
                  </p>
                  <Evidence value={item.evidence} />
                </li>
              ))}
            </ul>
          )}

          <h3 className="mt-7 text-lg font-semibold">Stale blockers</h3>
          {findings.stale_blockers.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">
              No stale blockers found.
            </p>
          ) : (
            <ul className="mt-3 space-y-3">
              {findings.stale_blockers.map((item) => (
                <li
                  key={item.task_id}
                  className="rounded-lg border border-slate-800 p-4"
                >
                  <p className="font-medium">{item.task_title}</p>
                  <p className="mt-1 text-sm text-slate-400">
                    Blocked for {item.days_blocked} day(s)
                  </p>
                  <Evidence value={item.evidence} />
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <h3 className="text-lg font-semibold">Critical path</h3>
          {criticalPath.tasks.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">
              No incomplete task path found.
            </p>
          ) : (
            <ol className="mt-3 space-y-2">
              {criticalPath.tasks.map((task, index) => (
                <li
                  key={task.id}
                  className="flex gap-3 rounded-lg border border-slate-800 p-3"
                >
                  <span className="text-slate-500">{index + 1}.</span>
                  <span>
                    <span className="font-medium">{task.title}</span>
                    <span className="ml-2 text-xs text-slate-400">
                      {task.status.replaceAll("_", " ")}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          )}

          <h3 className="mt-7 text-lg font-semibold">Recommendations</h3>
          {recommendations.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">
              No recommendations right now.
            </p>
          ) : (
            <ul className="mt-3 space-y-3">
              {recommendations.map((item, index) => (
                <li
                  key={`${item.type}-${index}`}
                  className="rounded-lg border border-slate-800 p-4"
                >
                  <p>{item.message}</p>
                  <p className="mt-2 text-xs text-slate-500">
                    {item.severity} · {item.type.replaceAll("_", " ")}
                  </p>
                  <Evidence value={item.evidence} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="mt-8 border-t border-slate-800 pt-6">
        <h3 className="text-lg font-semibold">Workload</h3>
        <p className="mt-1 text-xs text-slate-500">
          {summary.workload.disclaimer}
        </p>
        {summary.workload.workload.length === 0 ? (
          <p className="mt-3 text-sm text-slate-400">
            No assigned incomplete tasks.
          </p>
        ) : (
          <ul className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {summary.workload.workload.map((member) => (
              <li
                key={member.user_id}
                className="rounded-lg border border-slate-800 p-4"
              >
                <p className="font-medium">{member.username}</p>
                <p className="mt-1 text-sm text-slate-400">
                  {member.active_task_count} active task(s)
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
