/**
 * DRAFT legal pages (user decision: placeholder drafts until real text is provided).
 * Based on the backend's privacy design (backend/docs/SECURITY_AND_PRIVACY.md). Not legal advice.
 */
import type { ReactNode } from "react";

import { GlassPanel } from "@/components/glass/Glass";

function Draft({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-3xl px-4 pb-20 pt-32">
      <GlassPanel className="p-8 sm:p-10">
        <p className="mb-4 inline-flex rounded-full border border-warn/40 bg-warn/10 px-3 py-1 text-xs font-semibold text-warn">
          Draft, not legal advice
        </p>
        <h1 className="text-3xl">{title}</h1>
        <div className="mt-6 space-y-4 text-mist [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:text-ink">{children}</div>
      </GlassPanel>
    </div>
  );
}

export function TermsPage() {
  return (
    <Draft title="Terms of service">
      <p>
        SkillProof turns public GitHub activity into a skill card. By creating an account you agree to these
        terms.
      </p>
      <h2>Your account</h2>
      <p>
        Keep your credentials safe. Recruiter accounts are approved by an admin and may be suspended for
        misuse.
      </p>
      <h2>What we analyse</h2>
      <p>
        Only public repositories you own. Scores come from published rules; the AI-written summary never sets
        a number.
      </p>
      <h2>Recruiters</h2>
      <p>
        Recruiters must not harass candidates. Feedback with abusive language is held for review and may not
        be delivered.
      </p>
      <h2>Changes</h2>
      <p>We'll tell you about material changes by email and ask you to accept them again.</p>
    </Draft>
  );
}

export function PrivacyPage() {
  return (
    <Draft title="Privacy policy">
      <p>We follow the Kenya Data Protection Act, 2019. This page explains what we hold and your rights.</p>
      <h2>What we collect</h2>
      <p>
        Your name, email, optional phone number, your GitHub login and public repository statistics, and your
        consent choices.
      </p>
      <h2>Who sees it</h2>
      <p>
        Approved recruiters see your skill card if it's visible; never your email or phone. You can hide your
        card at any time.
      </p>
      <h2>Messages</h2>
      <p>
        Feedback by email or SMS (sender "SkillProof") only with your consent. Reply STOP to any SMS to opt
        out.
      </p>
      <h2>Your rights</h2>
      <p>
        Download everything we hold, or delete your account, from your settings. Old message bodies are erased
        after 180 days.
      </p>
    </Draft>
  );
}
