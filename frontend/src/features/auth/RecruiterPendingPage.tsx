import { Clock, ShieldX, XCircle } from "lucide-react";
import { Navigate } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { StatusChip } from "@/components/ui/Badge";
import { useAuth } from "@/lib/auth/auth-context";

import { AuthCard } from "./parts";

/** Pending, rejected or suspended recruiters land here; approved ones are sent on. */
export function RecruiterPendingPage() {
  const { user, signOut } = useAuth();
  const profile = user?.recruiterProfile;
  if (!user || !profile) return <Navigate to="/login" replace />;
  if (profile.approvalStatus === "approved") return <Navigate to="/recruiter" replace />;

  const status = profile.approvalStatus ?? "pending";
  const view = {
    pending: {
      icon: Clock,
      tone: "warn" as const,
      title: "Your account is waiting for approval",
      body: "An admin checks every recruiter before they can search candidates or send feedback. You'll get an email as soon as it's done.",
    },
    rejected: {
      icon: XCircle,
      tone: "bad" as const,
      title: "Your recruiter account wasn't approved",
      body: "If you think this is a mistake, reply to the email we sent with details of your company and role.",
    },
    suspended: {
      icon: ShieldX,
      tone: "bad" as const,
      title: "Your recruiter account is suspended",
      body: "Recruiter features are paused. Contact the SkillProof team to restore access.",
    },
  }[status];
  const Icon = view.icon;

  return (
    <AuthCard title={view.title}>
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-2">
          <StatusChip tone={view.tone}>
            {status === "pending" ? "Pending review" : status === "rejected" ? "Rejected" : "Suspended"}
          </StatusChip>
          <span className="text-sm text-mist">{profile.company?.name}</span>
        </div>
        <p className="flex gap-3 text-mist">
          <Icon aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-mist" />
          {view.body}
        </p>
        {profile.reviewNote && (
          <blockquote className="rounded-xl border border-line bg-white/[0.03] px-4 py-3 text-sm">
            <span className="text-mist">Note from the SkillProof team: </span>
            {profile.reviewNote}
          </blockquote>
        )}
        {!user.emailVerified && status === "pending" && (
          <p className="text-sm text-warn">Verify your email first: approval needs a confirmed address.</p>
        )}
        <Button variant="glass" className="w-full" onClick={() => signOut()}>
          Sign out
        </Button>
      </div>
    </AuthCard>
  );
}
