import { getServerSession } from "next-auth"
import { redirect } from "next/navigation"
import { authOptions } from "@/lib/auth"

export default async function Home() {
  const session = await getServerSession(authOptions)
  const hasAccessToken = Boolean((session as { accessToken?: string } | null)?.accessToken)

  redirect(hasAccessToken ? "/dashboard" : "/login")
}
