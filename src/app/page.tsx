import { redirect } from "next/navigation";

/** В этой ветке есть только раздел Tutor, поэтому главная ведёт на него. */
export default function HomePage() {
  redirect("/tutor");
}
