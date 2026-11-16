import { useQueryClient } from "@tanstack/react-query";

import { AuthShell } from "@/features/auth/AuthShell";
import { NameForm } from "@/features/community/NameForm";
import { supabase } from "@/lib/supabase";
import { TextLink } from "@/ui/components";

/**
 * Shown after sign-in, before anything else, until the person has chosen a username. The same
 * name is used everywhere (today only the chat shows it), so it is asked once, here.
 */
export function UsernameGate() {
  const queryClient = useQueryClient();
  return (
    <AuthShell title="One last step" subtitle="Choose the username other learners will see.">
      <NameForm plain onDone={() => void queryClient.invalidateQueries({ queryKey: ["community", "me"] })} />
      <TextLink label="Sign out" tone="danger" onPress={() => void supabase.auth.signOut()} />
    </AuthShell>
  );
}
