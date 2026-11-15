
import api from "./axios";
import type { Task, TaskStatus, TaskPriority } from "../types/task";

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface CreateTaskData {
  title: string;
  description?: string;
  priority: TaskPriority;
  assignee?: number | null;
  due_date?: string | null;
  labels?: number[];
}

export interface TaskLabel {
  id: number;
  name: string;
  color: string;
}
export interface UpdateTaskData {
  title?: string;
  description?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  assignee?: number | null;
  due_date?: string | null;
  labels?: number[];
}
export const getProjectTasks = async (
  projectId: number,
  status: TaskStatus,
  page: number = 1
): Promise<PaginatedResponse<Task>> => {
  const response = await api.get<PaginatedResponse<Task>>(
    `/projects/${projectId}/tasks/`,
    {
      params: {
        status,
        page,
        page_size: 20,
      },
    }
  );

  return response.data;
};

// Fetch every task belonging to a project, across all four statuses.
export const getAllProjectTasks = async (
  projectId: number
): Promise<Task[]> => {
  const statuses: TaskStatus[] = [
    "TODO",
    "IN_PROGRESS",
    "IN_REVIEW",
    "DONE",
  ];

  const tasksByStatus = await Promise.all(
    statuses.map(async (status) => {
      const allTasks: Task[] = [];
      let page = 1;
      let hasNextPage = true;

      while (hasNextPage) {
        const response = await getProjectTasks(
          projectId,
          status,
          page
        );

        allTasks.push(...response.results);
        hasNextPage = response.next !== null;
        page += 1;
      }

      return allTasks;
    })
  );

  return tasksByStatus.flat();
};

// Create a task inside a project.
export const createTask = async (
  projectId: number,
  data: CreateTaskData
): Promise<Task> => {
  const response = await api.post<Task>(
    `/projects/${projectId}/tasks/`,
    data
  );

  return response.data;
};

// Fetch labels belonging to a project.
export const getProjectLabels = async (
  projectId: number
): Promise<TaskLabel[]> => {
  const response = await api.get<TaskLabel[]>(
    `/projects/${projectId}/labels/`
  );

  return response.data;
};

export const updateTaskStatus = async (
  taskId: number,
  status: TaskStatus
): Promise<Task> => {
  const response = await api.patch<Task>(`/tasks/${taskId}/`, {
    status,
  });

  return response.data;
};
// Update task details.
export const updateTask = async (
  taskId: number,
  data: UpdateTaskData
): Promise<Task> => {
  const response = await api.patch<Task>(
    `/tasks/${taskId}/`,
    data
  );

  return response.data;
};