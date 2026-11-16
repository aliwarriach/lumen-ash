// The checking logic lives in the shared practice engine; grammar re-uses it unchanged.
export {
  filled,
  isCorrect,
  nearMiss,
  scrambleTiles,
  shuffle,
  type PracticeItem as Exercise,
} from "@/features/practice/check";
