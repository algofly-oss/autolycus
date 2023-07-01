import UserNavBar from "./components/NavBar";
import useTheme from "@/shared/hooks/useTheme";

export default function UserHome() {
  const theme = useTheme();
  return (
    <div className="flex w-full">
      <UserNavBar />
      <div className="border w-full">
        <p
          className="text-red-500 dark:text-blue-500 cursor-pointer"
          onClick={() => theme.toggleColorScheme()}
        >
          User Home - {theme.colorScheme}
        </p>
      </div>
    </div>
  );
}
