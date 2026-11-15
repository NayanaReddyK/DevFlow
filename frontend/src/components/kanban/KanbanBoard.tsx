
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import TaskDetailDrawer from "./TaskDetailDrawer";
import {
  DragDropContext,
  Droppable,
  Draggable,
  type DropResult,
} from "@hello-pangea/dnd";

import {
  createTask,
  getAllProjectTasks,
  getProjectLabels,
  updateTaskStatus,
  type TaskLabel,
} from "../../api/taskApi";

import type { ProjectMember } from "../../api/projectApi";
import type { Task, TaskStatus, TaskPriority } from "../../types/task";

const columns: { id: TaskStatus; title: string }[] = [
  { id: "TODO", title: "To Do" },
  { id: "IN_PROGRESS", title: "In Progress" },
  { id: "IN_REVIEW", title: "In Review" },
  { id: "DONE", title: "Done" },
];

interface KanbanBoardProps {
  projectId: number;
  members: ProjectMember[];
}

export default function KanbanBoard({
  projectId,
  members,
}: KanbanBoardProps) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [labels, setLabels] = useState<TaskLabel[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [labelError, setLabelError] = useState("");

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [savingTask, setSavingTask] = useState(false);
  const [createError, setCreateError] = useState("");

  // Create task form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("MEDIUM");
  const [assignee, setAssignee] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [selectedLabels, setSelectedLabels] = useState<number[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
    // Search and filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [assigneeFilter, setAssigneeFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");

  // Fetch tasks and project labels.
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError("");

        const taskData = await getAllProjectTasks(projectId);
        setTasks(taskData);

        try {
          const labelData = await getProjectLabels(projectId);
          setLabels(labelData);
          setLabelError("");
        } catch {
          setLabels([]);
          setLabelError("Unable to load project labels.");
        }
      } catch {
        setError("Unable to load tasks. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [projectId]);

  const resetForm = () => {
    setTitle("");
    setDescription("");
    setPriority("MEDIUM");
    setAssignee("");
    setDueDate("");
    setSelectedLabels([]);
    setCreateError("");
  };

  const handleLabelToggle = (labelId: number) => {
    setSelectedLabels((current) =>
      current.includes(labelId)
        ? current.filter((id) => id !== labelId)
        : [...current, labelId]
    );
  };

  const handleCreateTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!title.trim()) {
      setCreateError("Task title is required.");
      return;
    }

    try {
      setSavingTask(true);
      setCreateError("");
      setError("");

      await createTask(projectId, {
        title: title.trim(),
        description: description.trim(),
        priority,
        assignee: assignee ? Number(assignee) : null,
        due_date: dueDate || null,
        labels: selectedLabels,
      });

      // Fetch the latest board state after successful creation.
      const updatedTasks = await getAllProjectTasks(projectId);
      setTasks(updatedTasks);

      resetForm();
      setShowCreateForm(false);
    } catch {
      setCreateError("Unable to create task. Please check the details and try again.");
    } finally {
      setSavingTask(false);
    }
  };

  const handleDragEnd = async (result: DropResult) => {
    const { destination, source, draggableId } = result;
    
    if (!destination || destination.droppableId === source.droppableId) {
      return;
    }

    const taskId = Number(draggableId);
    const newStatus = destination.droppableId as TaskStatus;

    const previousTasks = tasks;

    // Update the UI immediately.
    setTasks((currentTasks) =>
      currentTasks.map((task) =>
        task.id === taskId ? { ...task, status: newStatus } : task
      )
    );

    try {
      await updateTaskStatus(taskId, newStatus);
      setError("");
    } catch {
      // Restore the previous state if the API request fails.
      setTasks(previousTasks);
      setError("Could not update task status. Please try again.");
    }
  };
  const filteredTasks = tasks.filter((task) => {
    const matchesSearch = task.title
      .toLowerCase()
      .includes(searchQuery.trim().toLowerCase());

    const matchesAssignee =
      !assigneeFilter || String(task.assignee) === assigneeFilter;

    const matchesPriority =
      !priorityFilter || task.priority === priorityFilter;

    return matchesSearch && matchesAssignee && matchesPriority;
  });

  const hasActiveFilters =
        searchQuery.trim() !== "" ||
        assigneeFilter !== "" ||
        priorityFilter !== "";

  const clearFilters = () => {
        setSearchQuery("");
        setAssigneeFilter("");
        setPriorityFilter("");
  };

  if (loading) {
    return <p className="p-6 text-gray-500">Loading tasks...</p>;
  }

  if (error && tasks.length === 0) {
    return <p className="p-6 text-red-600">{error}</p>;
  }

  return (
    <div className="p-6">
      {/* Board actions */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Project Tasks</h3>
          <p className="text-sm text-slate-400">
            {tasks.length} task{tasks.length === 1 ? "" : "s"} in this project
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            resetForm();
            setShowCreateForm(true);
          }}
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-500"
        >
          + Create Task
        </button>
      </div>

      {error && (
        <p role="alert" className="mb-4 text-sm text-red-400">
          {error}
        </p>
      )}
            {/* Search and Filters */}
      <div className="mb-6 grid grid-cols-1 gap-3 rounded-xl border border-slate-700 bg-slate-900 p-4 md:grid-cols-2 xl:grid-cols-4">
        {/* Search */}
        <input
          type="text"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="Search tasks by title..."
          aria-label="Search tasks by title"
          className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-2.5 text-sm text-white outline-none placeholder:text-slate-500 focus:border-blue-500"
        />

        {/* Assignee filter */}
        <select
          value={assigneeFilter}
          onChange={(event) => setAssigneeFilter(event.target.value)}
          aria-label="Filter tasks by assignee"
          className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-2.5 text-sm text-white outline-none focus:border-blue-500"
        >
          <option value="">All assignees</option>
          <option value="null">Unassigned</option>

          {members.map((member) => (
            <option key={member.user_id} value={String(member.user_id)}>
              {member.username}
            </option>
          ))}
        </select>

        {/* Priority filter */}
        <select
          value={priorityFilter}
          onChange={(event) => setPriorityFilter(event.target.value)}
          aria-label="Filter tasks by priority"
          className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-2.5 text-sm text-white outline-none focus:border-blue-500"
        >
          <option value="">All priorities</option>
          <option value="LOW">Low</option>
          <option value="MEDIUM">Medium</option>
          <option value="HIGH">High</option>
          <option value="CRITICAL">Critical</option>
        </select>

        {/* Clear filters */}
        <button
          type="button"
          onClick={clearFilters}
          disabled={!hasActiveFilters}
          className="rounded-lg border border-slate-600 px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Clear filters
        </button>
      </div>

      {hasActiveFilters && (
        <p className="mb-4 text-sm text-slate-400">
          Showing {filteredTasks.length} of {tasks.length} tasks
        </p>
      )}

      {/* Create Task Form */}
      {showCreateForm && (
        <div
          className="mb-8 rounded-xl border border-slate-700 bg-slate-900 p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-task-heading"
        >
          <div className="mb-6 flex items-center justify-between">
            <h3 id="create-task-heading" className="text-xl font-semibold">
              Create New Task
            </h3>

            <button
              type="button"
              onClick={() => {
                setShowCreateForm(false);
                resetForm();
              }}
              disabled={savingTask}
              aria-label="Close create task form"
              className="text-2xl text-slate-400 hover:text-white disabled:opacity-50"
            >
              ×
            </button>
          </div>

          <form onSubmit={handleCreateTask} className="space-y-5">
            {/* Title */}
            <div>
              <label htmlFor="task-title" className="mb-2 block text-sm text-slate-300">
                Task title *
              </label>

              <input
                id="task-title"
                type="text"
                required
                maxLength={200}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. Implement user authentication"
                disabled={savingTask}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white outline-none focus:border-blue-500"
              />
            </div>

            {/* Description */}
            <div>
              <label htmlFor="task-description" className="mb-2 block text-sm text-slate-300">
                Description
              </label>

              <textarea
                id="task-description"
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Describe what needs to be done..."
                disabled={savingTask}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white outline-none focus:border-blue-500"
              />
            </div>

            {/* Priority and Assignee */}
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="task-priority" className="mb-2 block text-sm text-slate-300">
                  Priority
                </label>

                <select
                  id="task-priority"
                  value={priority}
                  onChange={(event) =>
                    setPriority(event.target.value as TaskPriority)
                  }
                  disabled={savingTask}
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white"
                >
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                  <option value="CRITICAL">Critical</option>
                </select>
              </div>

              <div>
                <label htmlFor="task-assignee" className="mb-2 block text-sm text-slate-300">
                  Assign to
                </label>

                <select
                  id="task-assignee"
                  value={assignee}
                  onChange={(event) => setAssignee(event.target.value)}
                  disabled={savingTask}
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white"
                >
                  <option value="">Unassigned</option>

                  {members.map((member) => (
                    <option key={member.user_id} value={member.user_id}>
                      {member.username} ({member.email})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Due date */}
            <div>
              <label htmlFor="task-due-date" className="mb-2 block text-sm text-slate-300">
                Due date
              </label>

              <input
                id="task-due-date"
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
                disabled={savingTask}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-white outline-none focus:border-blue-500"
              />
            </div>

            {/* Labels */}
            <div>
              <p className="mb-3 text-sm text-slate-300">Labels</p>

              {labelError ? (
                <p className="text-sm text-amber-400">{labelError}</p>
              ) : labels.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No labels have been created for this project yet.
                </p>
              ) : (
                <div className="flex flex-wrap gap-3">
                  {labels.map((label) => (
                    <label
                      key={label.id}
                      className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        checked={selectedLabels.includes(label.id)}
                        onChange={() => handleLabelToggle(label.id)}
                        disabled={savingTask}
                        className="accent-blue-500"
                      />

                      <span
                        className="h-3 w-3 rounded-full"
                        style={{ backgroundColor: label.color }}
                      />

                      <span>{label.name}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* Form error */}
            {createError && (
              <p role="alert" className="text-sm text-red-400">
                {createError}
              </p>
            )}

            {/* Actions */}
            <div className="flex flex-wrap justify-end gap-3 border-t border-slate-700 pt-5">
              <button
                type="button"
                onClick={() => {
                  setShowCreateForm(false);
                  resetForm();
                }}
                disabled={savingTask}
                className="rounded-lg border border-slate-600 px-5 py-2.5 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50"
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={savingTask || !title.trim()}
                className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {savingTask ? "Creating..." : "Create Task"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Kanban Board */}
      <DragDropContext onDragEnd={handleDragEnd}>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
          {columns.map((column) => {
            const columnTasks = filteredTasks.filter(
              (task) => task.status === column.id
            );

            return (
              <div
                key={column.id}
                className="min-h-[450px] rounded-xl bg-gray-100 p-4"
              >
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="font-semibold text-gray-800">
                    {column.title}
                  </h3>

                  <span className="rounded-full bg-white px-3 py-1 text-sm text-gray-600">
                    {columnTasks.length}
                  </span>
                </div>

                <Droppable droppableId={column.id}>
                  {(provided, snapshot) => (
                    <div
                      ref={provided.innerRef}
                      {...provided.droppableProps}
                      
                      className={`min-h-[350px] space-y-3 rounded-lg transition-colors ${
                        snapshot.isDraggingOver ? "bg-blue-50" : ""
                      }`}
                    >
                      {columnTasks.map((task, index) => (
                        <Draggable
                          key={task.id}
                          draggableId={String(task.id)}
                          index={index}
                        >
                          {(provided, snapshot) => (
                            <div
                              ref={provided.innerRef}
                              {...provided.draggableProps}
                              {...provided.dragHandleProps}
                              onClick={() => setSelectedTask(task)}
                              role="button"
                              tabIndex={0}
                              onKeyDown={(event) => {
                                    if (event.key === "Enter" || event.key === " ") {
                                    event.preventDefault();
                                    setSelectedTask(task);
                                    }
                                }}
                              className={`rounded-lg border bg-white p-4 shadow-sm ${
                                snapshot.isDragging
                                  ? "shadow-lg"
                                  : "hover:shadow-md"
                              }`}
                            >
                              <div className="mb-2 flex items-start justify-between gap-2">
                                <h4 className="font-medium text-gray-900">
                                  {task.title}
                                </h4>

                                <span className="text-xs text-gray-400">
                                  #{task.id}
                                </span>
                              </div>

                              {task.description && (
                                <p className="mb-3 text-sm text-gray-500">
                                  {task.description}
                                </p>
                              )}

                              <div className="flex items-center justify-between">
                                <span
                                  className={`rounded-full px-2 py-1 text-xs font-medium ${
                                    task.priority === "CRITICAL"
                                      ? "bg-red-100 text-red-700"
                                      : task.priority === "HIGH"
                                      ? "bg-orange-100 text-orange-700"
                                      : task.priority === "MEDIUM"
                                      ? "bg-yellow-100 text-yellow-700"
                                      : "bg-green-100 text-green-700"
                                  }`}
                                >
                                  {task.priority}
                                </span>

                                {task.due_date && (
                                  <span className="text-xs text-gray-500">
                                    Due: {task.due_date}
                                  </span>
                                )}
                              </div>
                            </div>
                            
                          )}
                        </Draggable>
                      ))}

                      {provided.placeholder}

                      {columnTasks.length === 0 && (
                        <p className="py-8 text-center text-sm text-gray-400">
                          {hasActiveFilters
                            ? "No matching tasks"
                            : "No tasks yet"}
                        </p>
                      )}
                    </div>
                  )}
                </Droppable>
              </div>
            );
          })}
        </div>
      </DragDropContext>
      {selectedTask && (
  <TaskDetailDrawer
    task={selectedTask}
    members={members}
    labels={labels}
    onClose={() => setSelectedTask(null)}
    onSaved={(updatedTask) => {
      setTasks((currentTasks) =>
        currentTasks.map((task) =>
          task.id === updatedTask.id ? updatedTask : task
        )
      );

      setSelectedTask(updatedTask);
    }}
  />
)}
    </div>
  );
}
