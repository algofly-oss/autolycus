import { BiLogOut } from "react-icons/bi";
import { FiX } from "react-icons/fi";
import { useState } from "react";
import useAuth from "@/shared/hooks/useAuth";

export default function Logout({ collapsed = false }) {
  const auth = useAuth();
  const profilePictureShort = auth?.user?.profile_picture?.data_url || null;
  const [confirmOpen, setConfirmOpen] = useState(false);

  const handleLogout = () => {
    setConfirmOpen(false);
    auth.signOut({ redirect: true });
  };

  return (
    <>
      {collapsed ? (
        <button
          type="button"
          className="flex h-10 w-10 items-center justify-center rounded-md text-neutral-700 transition-colors hover:bg-zinc-200 dark:text-neutral-300 dark:hover:bg-zinc-900"
          onClick={() => setConfirmOpen(true)}
          title="Log out"
          aria-label="Log out"
        >
          <BiLogOut size={22} />
        </button>
      ) : (
      <div>
        <div
          className="flex items-center my-4 space-x-4 drop-shadow-md"
        >
          {profilePictureShort ? (
            <img
              src={profilePictureShort}
              alt="profile"
              className="h-12 w-12 object-cover rounded-full"
            />
          ) : (
            <div className="flex items-center justify-center h-12 w-12 rounded-full bg-blue-500 dark:bg-blue-700">
              <p className="text-2xl text-white">
                {(auth?.user?.name || " ").slice(0, 1).toUpperCase()}
              </p>
            </div>
          )}
          <div>
            <p className="text-sm font-bold">
              {auth?.user?.name
                ?.split(" ")
                .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
                .join(" ")}
            </p>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              {auth?.user?.username}
            </p>
          </div>
        </div>
        <div
          className="flex items-center space-x-4 bg-zinc-200 dark:bg-zinc-900 p-4 rounded-lg text-sm mt-2 justify-center cursor-pointer"
          onClick={() => setConfirmOpen(true)}
        >
          <BiLogOut size={20} />
          <p className="font-medium">Log out</p>
        </div>
      </div>
      )}

      {confirmOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[1px]"
            onClick={() => setConfirmOpen(false)}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="w-full max-w-sm rounded-lg bg-white dark:bg-[#1A1B1E] shadow-lg border border-zinc-200 dark:border-zinc-800">
              <div className="flex items-center justify-between p-4 border-b border-zinc-200 dark:border-zinc-800">
                <p className="text-sm font-semibold">Confirm logout</p>
                <button
                  type="button"
                  onClick={() => setConfirmOpen(false)}
                  className="p-1 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
                  aria-label="Cancel logout"
                >
                  <FiX size={16} />
                </button>
              </div>
              <div className="p-4">
                <p className="text-sm text-zinc-600 dark:text-zinc-300">
                  Are you sure you want to log out?
                </p>
                <div className="mt-5 flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setConfirmOpen(false)}
                    className="px-4 h-9 rounded-md text-sm bg-zinc-200 text-zinc-800 hover:bg-zinc-300 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700 transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="px-4 h-9 rounded-md text-sm bg-blue-600 text-white hover:bg-blue-700 transition"
                  >
                    Log out
                  </button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
