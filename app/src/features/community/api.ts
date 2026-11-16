import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { unwrap } from "@/api/errors";
import type { Attachment } from "@/features/community/ask";
import type { components } from "@/api/schema";

type Schemas = components["schemas"];
export type CommunityMe = Schemas["CommunityMeOut"];

/** Page size for the latest messages and for "load older". */
export const PAGE_SIZE = 50;

// Not kept on the phone: the app only saves `reviews` and `dashboard` (see app/_layout.tsx), so the
// chat and the person's name are fetched fresh and sign-out has nothing to clear.
const meKey = ["community", "me"] as const;

/** Who I am in the chat: my display name (null until chosen), whether I moderate, the limits. */
export function useCommunityMe() {
  return useQuery({
    queryKey: meKey,
    queryFn: async () => unwrap(await api.GET("/community/me")),
  });
}

/** Chooses or changes the display name. Fails with "Someone already uses that name" (409). */
export function useSetCommunityName() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (displayName: string) =>
      unwrap(await api.PUT("/community/me", { body: { display_name: displayName } })),
    onSuccess: (me) => queryClient.setQueryData(meKey, me),
  });
}

export async function fetchLatest() {
  return unwrap(await api.GET("/community/messages", { params: { query: { limit: PAGE_SIZE } } }));
}

export async function fetchOlder(before: number) {
  return unwrap(
    await api.GET("/community/messages", { params: { query: { before, limit: PAGE_SIZE } } }),
  );
}

export async function fetchChanges(after: number) {
  return unwrap(await api.GET("/community/changes", { params: { query: { after } } }));
}

/** Posts a message. Sending the same `id` again returns the saved message and posts nothing. */
export async function postMessage(message: {
  id: string;
  body: string;
  replyToId: string | null;
  /** What the question is about (Ask the Community). */
  attachment?: Attachment | null;
}) {
  return unwrap(
    await api.POST("/community/messages", {
      body: {
        id: message.id,
        body: message.body,
        reply_to_id: message.replyToId,
        attachment: message.attachment ?? null,
      },
    }),
  );
}

/** Deletes a message (mine, or anyone's for a moderator). Returns it as deleted. */
export async function deleteMessage(id: string) {
  return unwrap(await api.DELETE("/community/messages/{message_id}", { params: { path: { message_id: id } } }));
}
