import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, FolderLock, Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { api, jsonBody } from "../api/client";
import { Button, Empty, ErrorNotice, Field, Panel, Status } from "../components/Ui";
import type { Project } from "../types";

function formText(data: FormData, name: string): string {
  const value = data.get(name);
  return typeof value === "string" ? value : "";
}

export function Dashboard() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/projects"),
  });
  const createProject = useMutation({
    mutationFn: (payload: { name: string; description: string }) =>
      api<Project>("/projects", { method: "POST", ...jsonBody(payload) }),
    onSuccess: async () => {
      setCreating(false);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    createProject.mutate({
      name: formText(values, "name"),
      description: formText(values, "description"),
    });
  }

  return (
    <main id="main-content" className="page">
      <div className="page-title">
        <div>
          <p className="eyebrow">Authorized workspace</p>
          <h1>Projects</h1>
          <p>Every target, profile, request, run, finding, and report is project-scoped.</p>
        </div>
        <Button onClick={() => { setCreating((value) => !value); }}>
          <Plus aria-hidden="true" size={16} /> New project
        </Button>
      </div>
      <ErrorNotice error={projects.error ?? createProject.error} />
      {creating && (
        <Panel title="Create project" description="Use a factual name that identifies the approved engagement.">
          <form className="form-grid" onSubmit={submit}>
            <Field label="Project name">
              <input name="name" required maxLength={160} />
            </Field>
            <Field label="Description">
              <textarea name="description" rows={3} maxLength={10_000} />
            </Field>
            <Button type="submit" disabled={createProject.isPending}>
              Create project
            </Button>
          </form>
        </Panel>
      )}
      <section className="card-grid" aria-label="Project list">
        {projects.data?.map((project) => (
          <article className="project-card" key={project.id}>
            <FolderLock aria-hidden="true" />
            <div>
              <h2>{project.name}</h2>
              <p>{project.description || "No description supplied."}</p>
              <Status value={project.status} />
            </div>
            <Link to={`/projects/${project.id}/targets`}>
              Open workspace <ArrowRight aria-hidden="true" size={16} />
            </Link>
          </article>
        ))}
      </section>
      {!projects.isLoading && projects.data?.length === 0 && (
        <Empty>No projects yet. Create one to begin a controlled comparison.</Empty>
      )}
    </main>
  );
}
