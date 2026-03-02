import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { ProjectCreate, ProjectResponse } from "@/types";
import { projectService } from "@/services/projectService";
import { useAuth } from "./AuthContext";

interface ProjectContextType {
  projects: ProjectResponse[];
  currentProject: ProjectResponse | null;
  isLoading: boolean;
  selectProject: (project: ProjectResponse) => void;
  refreshProjects: () => Promise<void>;
  createProject: (data: ProjectCreate) => Promise<ProjectResponse>;
}

const ProjectContext = createContext<ProjectContextType | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [currentProject, setCurrentProject] =
    useState<ProjectResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const refreshProjects = useCallback(async () => {
    setIsLoading(true);
    try {
      const list = await projectService.list();
      setProjects(list);

      const savedId = localStorage.getItem("forgeline_project_id");
      const saved = savedId ? list.find((p) => p.id === savedId) : null;

      if (saved) {
        setCurrentProject(saved);
      } else if (list.length > 0 && !currentProject) {
        setCurrentProject(list[0]);
        localStorage.setItem("forgeline_project_id", list[0].id);
      }
    } catch {
      // Silently fail - user can create project later
    } finally {
      setIsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      refreshProjects();
    } else {
      setProjects([]);
      setCurrentProject(null);
    }
  }, [isAuthenticated, refreshProjects]);

  const selectProject = useCallback((project: ProjectResponse) => {
    setCurrentProject(project);
    localStorage.setItem("forgeline_project_id", project.id);
  }, []);

  const createProject = useCallback(
    async (data: ProjectCreate): Promise<ProjectResponse> => {
      const project = await projectService.create(data);
      setProjects((prev) => [project, ...prev]);
      setCurrentProject(project);
      localStorage.setItem("forgeline_project_id", project.id);
      return project;
    },
    [],
  );

  return (
    <ProjectContext.Provider
      value={{
        projects,
        currentProject,
        isLoading,
        selectProject,
        refreshProjects,
        createProject,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject(): ProjectContextType {
  const ctx = useContext(ProjectContext);
  if (!ctx) {
    throw new Error("useProject must be used within ProjectProvider");
  }
  return ctx;
}
