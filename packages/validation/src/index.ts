import { z } from "zod";
export const stateCode = z
  .string()
  .length(2)
  .transform((value) => value.toUpperCase());
