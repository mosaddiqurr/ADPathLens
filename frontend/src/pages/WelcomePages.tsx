import {
  ArrowRight,
  ArrowUpRight,
  Crown,
  FileSearch,
  GitBranch,
  Network,
  Server,
  ShieldCheck,
  UserRound,
  Users,
  Wrench,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Reveal } from "../components/visual/Reveal";
import { HeroTopology } from "../components/visual/HeroTopology";
import { useAppearance } from "../features/appearance/AppearanceContext";
import { PageHeading } from "./ProductPages";

const example = [
  {
    name: "User A",
    type: "User",
    Icon: UserRound,
    relationship: "Member of",
  },
  { name: "Helpdesk", type: "Group", Icon: Users, relationship: "Local admin" },
  {
    name: "NB-HELPDESK-01",
    type: "Computer",
    Icon: Server,
    relationship: "Has session",
  },
  {
    name: "User B",
    type: "Privileged user",
    Icon: UserRound,
    relationship: "Member of",
  },
  {
    name: "Domain Admins",
    type: "Privileged target",
    Icon: Crown,
    relationship: "",
  },
];

export function HomePage() {
  return (
    <div className="page home-page">
      <section className="hero">
        <Reveal className="hero-copy">
          <p className="eyebrow hero-eyebrow">
            <GitBranch size={14} />
            Active Directory attack-path analysis
          </p>
          <h1>
            Find the path.<span>Break the chain.</span>
          </h1>
          <p className="hero-description">
            Trace hidden routes to privileged access, inspect the evidence, and
            find the relationships worth fixing.
          </p>
          <div className="button-row">
            <Link className="primary-button" to="/analyze">
              Analyze AD data
              <ArrowUpRight size={18} />
            </Link>
            <Link className="secondary-button" to="/analyze?demo=1">
              <Network size={17} />
              Load demo
            </Link>
          </div>
        </Reveal>
        <Reveal className="hero-art" delay={0.12}>
          <HeroTopology />
          <div className="topology-caption">
            <span>Follow the access.</span>
            <span>Find the exposure.</span>
          </div>
        </Reveal>
      </section>
      <Reveal className="home-boundary">
        <ShieldCheck size={16} />
        <p>Defensive analysis. Evidence at every step.</p>
        <span>JSON / CSV / ZIP</span>
        <Link to="/about">
          Understand the methodology
          <ArrowRight size={14} />
        </Link>
      </Reveal>
      <Reveal className="route-story">
        <div className="route-story-heading">
          <div>
            <h2>One relationship changes the picture.</h2>
            <p>
              An ordinary identity can be closer to privileged access than it
              looks.
            </p>
          </div>
          <span className="example-label">Illustrative access path</span>
        </div>
        <div
          aria-label="Example attack chain with fictional identities"
          className="route-example"
        >
          <ol className="topology-chain">
            {example.map(({ name, type, Icon, relationship }, index) => (
              <li
                key={name}
                className={index === example.length - 1 ? "is-target" : ""}
              >
                <div className="topology-node">
                  <Icon size={22} strokeWidth={1.5} />
                </div>
                <strong>{name}</strong>
                <small>{type}</small>
                {relationship && (
                  <div className="topology-link">
                    <span>{relationship}</span>
                    <ArrowRight size={14} />
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
        <div className="route-story-footer">
          <GitBranch size={15} />
          <span>
            Every step has a relationship. Every relationship deserves context.
          </span>
        </div>
      </Reveal>
      <section className="capabilities" aria-label="Core capabilities">
        <Reveal className="capability-lead">
          <article>
            <FileSearch
              className="capability-icon"
              size={25}
              strokeWidth={1.5}
            />
            <h2>
              Evidence.
              <br />
              Not assumptions.
            </h2>
            <p>
              Follow the imported relationships behind a path. Review source
              evidence and confidence before drawing conclusions.
            </p>
            <div className="evidence-principles">
              <span>
                <ShieldCheck size={15} />
                Source evidence
              </span>
              <span>
                <GitBranch size={15} />
                Ordered relationships
              </span>
              <span>
                <FileSearch size={15} />
                Confidence & context
              </span>
            </div>
          </article>
        </Reveal>
        <Reveal className="capability-secondary" delay={0.06}>
          <article>
            <GitBranch size={24} strokeWidth={1.5} />
            <div>
              <h2>Find privilege paths</h2>
              <p>
                Trace users, groups, and computers toward the assets that
                matter.
              </p>
            </div>
            <ArrowUpRight size={18} />
          </article>
        </Reveal>
        <Reveal className="capability-secondary" delay={0.1}>
          <article>
            <Wrench size={24} strokeWidth={1.5} />
            <div>
              <h2>Prioritize remediation</h2>
              <p>
                Start with dangerous paths and the permissions shared across
                them. Export the findings for review.
              </p>
            </div>
            <ArrowUpRight size={18} />
          </article>
        </Reveal>
      </section>
      <Reveal className="workflow-strip">
        <div className="workflow-description">
          <strong>A clearer path from data to action.</strong>
          <small>Import. Inspect. Understand. Review.</small>
        </div>
        <div className="workflow-journey" aria-label="Product workflow">
          {["AD data", "Attack paths", "Evidence", "Remediation"].map(
            (name, index) => (
              <span key={name}>
                {name}
                {index < 3 && <ArrowRight size={14} aria-hidden="true" />}
              </span>
            ),
          )}
        </div>
      </Reveal>
    </div>
  );
}

export function AboutPage() {
  const { reduceMotion, toggleMotion } = useAppearance();
  return (
    <div className="page about-page">
      <PageHeading
        label="Methodology & scope"
        title="About ADPathLens"
        description="A focused tool for explaining how imported Active Directory relationships can create routes to privileged assets."
      />
      <div className="about-grid">
        <section className="panel">
          <h2>How to read an attack path</h2>
          <p>
            A path connects directory objects through modeled access or control
            relationships. An arrow shows the direction an attacker could move
            if each relationship is valid and its prerequisites are met.
          </p>
          <p>
            The graph, step explanations, and evidence refer to the same
            imported snapshot. Confidence describes the source evidence and
            influences relationship cost. The score helps prioritize review.
          </p>
          <h3>Review priority</h3>
          <p>
            Scores favor shorter routes with lower relationship costs. These
            bands help order review; the score is not a probability of
            exploitation.
          </p>
          <table className="priority-table">
            <caption className="sr-only">Path review priority bands</caption>
            <thead>
              <tr>
                <th scope="col">Priority</th>
                <th scope="col">Score / 100</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["critical", "85–100"],
                ["high", "65–84"],
                ["medium", "35–64"],
                ["low", "0–34"],
              ].map(([severity, range]) => (
                <tr key={severity}>
                  <th scope="row">
                    <span className={`severity severity-${severity}`}>
                      {severity}
                    </span>
                  </th>
                  <td>{range}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="panel">
          <h2>Evidence before conclusions</h2>
          <ul className="plain-list">
            <li>
              Paths suggest possible privilege exposure. They do not establish
              compromise or prove an exploit will succeed.
            </li>
            <li>
              Results are bounded by depth, confidence, time, and the returned
              path limit. A clean result applies to that scope.
            </li>
            <li>
              Imports are snapshots. Missing, stale, or incorrect relationships
              can change the result.
            </li>
            <li>
              Remediation recommendations require directory-owner review.
              ADPathLens does not execute changes.
            </li>
          </ul>
          <h3>Authorized inputs</h3>
          <p>
            Use synthetic data or data from systems you own or are explicitly
            authorized to assess. The app accepts ADPathLens JSON, paired CSV
            files, and constrained CSV ZIP archives. Collector exports require
            conversion.
          </p>
          <a className="text-link" href="/northbridge-demo.json" download>
            Download the fictional example
            <ArrowRight size={14} />
          </a>
        </section>
      </div>
      <section className="about-foundation">
        <div>
          <ShieldCheck size={21} />
          <h2>Built around the evidence.</h2>
          <p>
            React and Cytoscape present a FastAPI service backed by NetworkX and
            SQLite. Validation, session protection, CSRF, and data ownership
            checks stay behind every analysis.
          </p>
        </div>
        <div>
          <h3>Local portfolio mode</h3>
          <p>
            The local launcher uses a dedicated analyst session on loopback.
            Shared deployments retain account authentication. Imported snapshots
            and generated reports are stored by your ADPathLens server.
          </p>
          <small>ADPathLens is available under the MIT License.</small>
        </div>
      </section>
      <details className="accessibility-preferences">
        <summary>Accessibility preferences</summary>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={reduceMotion}
            onChange={toggleMotion}
            aria-describedby="motion-preference-help"
          />
          Reduce animations
        </label>
        <p id="motion-preference-help">
          Stops decorative motion and transitions. Your choice is saved in this
          browser.
        </p>
      </details>
      <Link className="primary-button" to="/analyze">
        Start an analysis
        <ArrowRight size={16} />
      </Link>
    </div>
  );
}
