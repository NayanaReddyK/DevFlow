
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type {
  Task,
  TaskStatus,
  TaskPriority,
} from "../../types/task";
import {
  addTaskDependency,
  deleteTask,
  getTaskDependencies,
  removeTaskDependency,
  updateTask,
  type TaskDependencies,
  type TaskLabel,
} from "../../api/taskApi";
import type { ProjectMember } from "../../api/projectApi";

interface TaskDetailDrawerProps {
  task: Task;
  projectTasks: Task[];
  members: ProjectMember[];
  labels: TaskLabel[];
  canDeleteTasks: boolean;
  canManageDependencies: boolean;
  onClose: () => void;
  onSaved: (updatedTask: Task) => void;
  onDeleted: (taskId: number) => void;
}

const statusOptions: { value: TaskStatus; label: string }[] = [
  { value: "TODO", label: "To Do" },
  { value: "IN_PROGRESS", label: "In Progress" },
  { value: "IN_REVIEW", label: "In Review" },
  { value: "DONE", label: "Done" },
];

const priorityOptions: { value: TaskPriority; label: string }[] = [
  { value: "LOW", label: "Low" },
  { value: "MEDIUM", label: "Medium" },
  { value: "HIGH", label: "High" },
  { value: "CRITICAL", label: "Critical" },
];

export default function TaskDetailDrawer({
  task,
  projectTasks,
  members,
  labels,
  canDeleteTasks,
  canManageDependencies,
  onClose,
  onSaved,
  onDeleted,
}: TaskDetailDrawerProps) {
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description ?? "");
  const [status, setStatus] = useState<TaskStatus>(task.status);
  const [priority, setPriority] = useState<TaskPriority>(task.priority);
  const [assignee, setAssignee] = useState(
    task.assignee === null ? "" : String(task.assignee)
  );
  const [dueDate, setDueDate] = useState(task.due_date ?? "");
  const [selectedLabels, setSelectedLabels] = useState<number[]>(
    task.labels ?? []
  );
  const [dependencies, setDependencies] = useState<TaskDependencies | null>(null);
  const [dependenciesLoading, setDependenciesLoading] = useState(true);
  const [dependenciesError, setDependenciesError] = useState("");
  const [newPrerequisiteId, setNewPrerequisiteId] = useState("");
  const [dependencySaving, setDependencySaving] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);

const handleDelete = async () => {
  const confirmed = window.confirm(
    `Permanently delete "${task.title}"? Its activity history and dependency links will also be deleted.`
  );

  if (!confirmed) return;

  try {
    setDeleting(true);
    setError("");
    await deleteTask(task.id);
    onDeleted(task.id);
  } catch {
    setError("Unable to delete this task. Check your permissions and project status.");
  } finally {
    setDeleting(false);
  }
};

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !saving) {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, saving]);
  useEffect(() => {
  let current = true;

  getTaskDependencies(task.id)
    .then((result) => {
      if (current) setDependencies(result);
    })
    .catch(() => {
      if (current) setDependenciesError("Unable to load task dependencies.");
    })
    .finally(() => {
      if (current) setDependenciesLoading(false);
    });

  return () => {
    current = false;
  };
}, [task.id]);

  const availablePrerequisites = projectTasks.filter(
    (candidate) =>
      candidate.id !== task.id &&
      !dependencies?.prerequisites.some(
        (dependency) => dependency.prerequisite_task_id === candidate.id
      )
  );

  const refreshDependencies = async () => {
    const updatedDependencies = await getTaskDependencies(task.id);
    setDependencies(updatedDependencies);
  };

  const handleAddPrerequisite = async () => {
    if (!newPrerequisiteId) return;

    try {
      setDependencySaving(true);
      setDependenciesError("");
      await addTaskDependency(task.id, Number(newPrerequisiteId));
      setNewPrerequisiteId("");
      await refreshDependencies();
    } catch {
      setDependenciesError(
        "Unable to add prerequisite. It may create a cycle, or you may not have permission."
      );
    } finally {
      setDependencySaving(false);
    }
  };

  const handleRemovePrerequisite = async (dependencyId: number) => {
    try {
      setDependencySaving(true);
      setDependenciesError("");
      await removeTaskDependency(task.id, dependencyId);
      await refreshDependencies();
    } catch {
      setDependenciesError("Unable to remove prerequisite.");
    } finally {
      setDependencySaving(false);
    }
  };

  const toggleLabel = (labelId: number) => {
    setSelectedLabels((current) =>
      current.includes(labelId)
        ? current.filter((id) => id !== labelId)
        : [...current, labelId]
    );
  };

  const handleSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!title.trim()) {
      setError("Task title is required.");
      return;
    }

    try {
      setSaving(true);
      setError("");

      const updatedTask = await updateTask(task.id, {
        title: title.trim(),
        description: description.trim(),
        status,
        priority,
        assignee: assignee ? Number(assignee) : null,
        due_date: dueDate || null,
        labels: selectedLabels,
      });

      onSaved(updatedTask);
    } catch {
      setError("Unable to save task changes. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const inputClass =
    "w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500 disabled:opacity-50";

  const labelClass = "mb-2 block text-sm font-medium text-slate-300";

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/50"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !saving) {
          onClose();
        }
      }}
    >
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="task-detail-heading"
        className="flex h-full w-full max-w-xl flex-col border-l border-slate-700 bg-slate-950 shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 px-6 py-5">
          <div>
            <p className="text-xs text-slate-500">TASK #{task.id}</p>
            <h2
              id="task-detail-heading"
              className="mt-1 text-xl font-semibold text-white"
            >
              Task details
            </h2>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            aria-label="Close task details"
            className="rounded-lg px-3 py-2 text-2xl text-slate-400 hover:bg-slate-800 hover:text-white disabled:opacity-50"
          >
            ×
          </button>
        </div>

        {/* Editable fields */}
        <form
          onSubmit={handleSave}
          className="flex min-h-0 flex-1 flex-col"
        >
          <div className="flex-1 space-y-5 overflow-y-auto p-6">
            <div>
              <label htmlFor="detail-title" className={labelClass}>
                Task title *
              </label>
              <input
                id="detail-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                maxLength={200}
                required
                disabled={saving}
                className={inputClass}
              />
            </div>

            <div>
              <label htmlFor="detail-description" className={labelClass}>
                Description
              </label>
              <textarea
                id="detail-description"
                rows={5}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                disabled={saving}
                className={inputClass}
              />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="detail-status" className={labelClass}>
                  Status
                </label>
                <select
                  id="detail-status"
                  value={status}
                  onChange={(event) =>
                    setStatus(event.target.value as TaskStatus)
                  }
                  disabled={saving}
                  className={inputClass}
                >
                  {statusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="detail-priority" className={labelClass}>
                  Priority
                </label>
                <select
                  id="detail-priority"
                  value={priority}
                  onChange={(event) =>
                    setPriority(event.target.value as TaskPriority)
                  }
                  disabled={saving}
                  className={inputClass}
                >
                  {priorityOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label htmlFor="detail-assignee" className={labelClass}>
                Assignee
              </label>
              <select
                id="detail-assignee"
                value={assignee}
                onChange={(event) => setAssignee(event.target.value)}
                disabled={saving}
                className={inputClass}
              >
                <option value="">Unassigned</option>
                {members.map((member) => (
                  <option key={member.user_id} value={member.user_id}>
                    {member.username} ({member.email})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="detail-due-date" className={labelClass}>
                Due date
              </label>
              <input
                id="detail-due-date"
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
                disabled={saving}
                className={inputClass}
              />
            </div>

            <div>
              <p className={labelClass}>Labels</p>

              {labels.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No project labels available.
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {labels.map((label) => {
                    const selected = selectedLabels.includes(label.id);

                    return (
                      <button
                        key={label.id}
                        type="button"
                        onClick={() => toggleLabel(label.id)}
                        disabled={saving}
                        aria-pressed={selected}
                        className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm ${
                          selected
                            ? "border-blue-500 bg-blue-500/15 text-white"
                            : "border-slate-700 text-slate-400 hover:border-slate-500"
                        }`}
                      >
                        <span
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ backgroundColor: label.color }}
                        />
                        {label.name}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="space-y-4 border-t border-slate-800 pt-4">
  <h3 className="font-semibold text-white">Dependencies</h3>

  {dependenciesLoading && (
    <p className="text-sm text-slate-400">Loading dependencies...</p>
  )}

  {dependenciesError && (
    <p role="alert" className="text-sm text-red-400">
      {dependenciesError}
    </p>
  )}

  {dependencies && (
    <>
      <div>
        <h4 className="text-sm font-medium text-slate-300">Prerequisites</h4>
        {dependencies.prerequisites.length === 0 ? (
          <p className="mt-1 text-sm text-slate-500">
            This task has no prerequisites.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {dependencies.prerequisites.map((item) => (
              <li
                key={item.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-slate-800 p-3 text-sm"
              >
                <span>
                  <span className="text-white">{item.prerequisite_task_title}</span>
                  <span className="ml-2 text-slate-400">
                    {item.prerequisite_task_status.replaceAll("_", " ")}
                  </span>
                </span>
                {canManageDependencies && (
                  <button
                    type="button"
                    onClick={() => handleRemovePrerequisite(item.id)}
                    disabled={dependencySaving}
                    className="shrink-0 text-xs text-red-400 hover:text-red-300 disabled:opacity-50"
                  >
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        {canManageDependencies && (
          <div className="mt-3 flex gap-2">
            <select
              aria-label="Choose prerequisite task"
              value={newPrerequisiteId}
              onChange={(event) => setNewPrerequisiteId(event.target.value)}
              disabled={
                dependencySaving || availablePrerequisites.length === 0
              }
              className={inputClass}
            >
              <option value="">
                {availablePrerequisites.length === 0
                  ? "No available prerequisite tasks"
                  : "Choose a prerequisite task"}
              </option>
              {availablePrerequisites.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  #{candidate.id} — {candidate.title}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleAddPrerequisite}
              disabled={dependencySaving || !newPrerequisiteId}
              className="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium disabled:opacity-50"
            >
              {dependencySaving ? "Saving..." : "Add"}
            </button>
          </div>
        )}
      </div>

      <div>
        <h4 className="text-sm font-medium text-slate-300">Dependents</h4>
        {dependencies.dependents.length === 0 ? (
          <p className="mt-1 text-sm text-slate-500">
            No tasks are waiting on this task.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {dependencies.dependents.map((item) => (
              <li
                key={item.id}
                className="rounded-lg border border-slate-800 p-3 text-sm text-white"
              >
                {item.dependent_task_title}
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  )}
</div>
            {/* Timestamps */}
            <div className="space-y-1 border-t border-slate-800 pt-4 text-xs text-slate-500">
              <p>
                Created: {new Date(task.created_at).toLocaleString()}
              </p>
              <p>
                Last updated: {new Date(task.updated_at).toLocaleString()}
              </p>
            </div>

            {error && (
              <p role="alert" className="text-sm text-red-400">
                {error}
              </p>
            )}
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 border-t border-slate-800 p-5">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg border border-slate-700 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50"
            >
              Cancel
            </button>
            {canDeleteTasks && (
  <button
    type="button"
    onClick={handleDelete}
    disabled={saving || deleting}
    className="mr-auto rounded-lg border border-red-900 px-4 py-2.5 text-sm text-red-400 hover:bg-red-950 disabled:opacity-50"
  >
    {deleting ? "Deleting..." : "Delete task"}
  </button>
)}
            <button
              type="submit"
              disabled={saving || !title.trim()}
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save changes"}
            </button>
          </div>
        </form>
      </aside>
    </div>
  );
}
