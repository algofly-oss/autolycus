import UserHome from "@/components/User";
import useAuth from "@/shared/hooks/useAuth";
import uiRoutes from "@/shared/routes/uiRoutes";
import { useRouter } from "next/router";
import { useEffect } from "react";

export default function App(props: any) {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    auth.getAccountInfo().then((data) => {
      if (data?.role !== "admin" && data?.role !== "user") {
        router.push(uiRoutes.signIn);
      }
    });
  }, []);

  return <UserHome />;
}
