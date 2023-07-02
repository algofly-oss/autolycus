import { BiLogOut } from "react-icons/bi";
import useAuth from "@/shared/hooks/useAuth";

export default function Logout() {
  const auth = useAuth();
  const profilePictureShort = null;

  return (
    <>
      <div>
        <div
          className="flex items-center my-4 space-x-4 cursor-pointer drop-shadow-md"
          onClick={() => setSelectedItem("profile")}
        >
          {profilePictureShort ? (
            <Image
              src={profilePictureShort}
              alt="profile"
              width="50px"
              height="50px"
              className="h-12 w-12 object-cover rounded-full"
            />
          ) : (
            <div className="flex items-center justify-center h-12 w-12 rounded-full bg-blue-500 dark:bg-blue-700">
              <p className="text-2xl text-white">
                {(auth?.user?.name || " ").slice(0, 1)}
              </p>
            </div>
          )}
          <div>
            <p className="text-sm font-bold">{auth?.user?.name}</p>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              {auth?.user?.username}
            </p>
          </div>
        </div>
        <div
          className="flex items-center space-x-4 bg-zinc-200 dark:bg-zinc-900 p-4 rounded-lg text-sm mt-2 justify-center cursor-pointer"
          onClick={() => auth.signOut({ redirect: true })}
        >
          <BiLogOut size={20} />
          <p className="font-medium">Log out</p>
        </div>
      </div>
    </>
  );
}
