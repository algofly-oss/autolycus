import { useEffect } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import useAuth from "@/shared/hooks/useAuth";

export default function App(props: any) {
  const router = useRouter();
  const auth = useAuth();

  useEffect(() => {
    // router.push("/home");
  }, []);

  return (
    <div className="flex space-x-2">
      {auth?.user?.username ? (
        <>
          <button onClick={() => auth.signOut({ redirect: true })}>
            Sign Out
          </button>
        </>
      ) : (
        <Link href="/account/signin">Sign In</Link>
      )}
    </div>
  );
}
