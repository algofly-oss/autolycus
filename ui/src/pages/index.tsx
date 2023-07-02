import { useEffect } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import useAuth from "@/shared/hooks/useAuth";
import uiRoutes from "@/shared/routes/uiRoutes";

export default function App(props: any) {
  const router = useRouter();
  const auth = useAuth();

  useEffect(() => {
    auth.autoRoute();
  }, []);

  return (
    <div className="flex space-x-2">
      {/* {auth?.user?.username ? (
        <>
          <button onClick={() => router.push(uiRoutes.home)}>Account</button>
          <button onClick={() => auth.signOut({ redirect: true })}>
            Sign Out
          </button>
        </>
      ) : (
        <Link href={uiRoutes.signIn} passHref>
          Sign In
        </Link>
      )} */}
    </div>
  );
}
