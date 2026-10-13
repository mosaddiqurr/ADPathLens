import { ArrowDownLeft, ArrowLeftRight, ArrowRight, ArrowUpRight, FileText, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

import logo from "../../../assets/logo-authzdiff.png";

export function Home() {
  return (
    <main id="main-content" className="workspace home-page">
      <div className="home-intro">
        <img className="home-logo" src={logo} alt="" />
        <p className="eyebrow">Authorization comparison</p>
        <h1>AuthZDiff</h1>
        <p className="page-description home-description">Compare authorization states and identify risky access changes.</p>
        <Link className="button primary" to="/compare">
          Compare access <ArrowRight size={17} aria-hidden="true" />
        </Link>
      </div>

      <section className="home-overview" aria-label="Before plus After reveals what changed">
        <div className="home-workflow">
          <div className="workflow-stage">
            <span className="workflow-icon"><FileText size={18} aria-hidden="true" /></span>
            <div><strong>Before</strong><span>Baseline</span></div>
          </div>
          <span className="workflow-symbol" aria-hidden="true">+</span>
          <div className="workflow-stage">
            <span className="workflow-icon"><FileText size={18} aria-hidden="true" /></span>
            <div><strong>After</strong><span>Candidate</span></div>
          </div>
          <ArrowRight className="workflow-arrow" size={18} aria-hidden="true" />
          <div className="workflow-stage workflow-result">
            <span className="workflow-icon"><ArrowLeftRight size={18} aria-hidden="true" /></span>
            <div><strong>What changed?</strong><span>Authorization changes</span></div>
          </div>
        </div>
        <ul className="home-features">
          <li>
            <span className="feature-icon"><ArrowUpRight size={18} aria-hidden="true" /></span>
            <div><strong>Access gained</strong><span>New or broader access</span></div>
          </li>
          <li>
            <span className="feature-icon"><ArrowDownLeft size={18} aria-hidden="true" /></span>
            <div><strong>Access lost</strong><span>Removed or reduced access</span></div>
          </li>
          <li>
            <span className="feature-icon"><ShieldAlert size={18} aria-hidden="true" /></span>
            <div><strong>Risky privilege changes</strong><span>Changes worth reviewing</span></div>
          </li>
        </ul>
      </section>
      <p className="home-note">Add two inputs. Review the changes. Export a report.</p>
    </main>
  );
}
