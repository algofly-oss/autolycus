import useAuth from "@/shared/hooks/useAuth";

export default function App(props: any) {
  const auth = useAuth();
  auth.autoRoute();

  return null;
}
