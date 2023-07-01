import UserHome from "@/components/User";
import useAuth from "@/shared/hooks/useAuth";
import { useEffect } from "react";

export default function App(props: any) {
  const auth = useAuth();

  useEffect(() => {
    auth.autoRoute();
  }, [auth]);

  return <UserHome />;
}
