import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { useDispatch } from "react-redux";
import { FiRefreshCw, FiTrash2, FiUpload } from "react-icons/fi";
import { FaSignOutAlt } from "react-icons/fa";
import apiRoutes from "@/shared/routes/apiRoutes";
import { syncCurrentSessionPublicIp } from "@/shared/sessionPublicIp";
import useAuth from "@/shared/hooks/useAuth";
import useToast from "@/shared/hooks/useToast";
import { authActions } from "@/redux/features/authSlice";

const settingsPanelClass =
  "rounded-lg border border-neutral-200 bg-white dark:border-[#33363b] dark:bg-[#202124]";
const settingsDividerClass = "border-neutral-200 dark:border-[#33363b]";
const accountInputClass =
  "mt-1 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 outline-none ring-0 focus:border-neutral-300 focus:outline-none focus:ring-0 dark:border-[#33363b] dark:bg-[#18191b] dark:text-neutral-100 dark:focus:border-[#33363b]";
const MAX_PROFILE_PICTURE_BYTES = 10 * 1024 * 1024;
const ALLOWED_PROFILE_PICTURE_TYPES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
]);
const relativeTimeFormatter = new Intl.RelativeTimeFormat(undefined, {
  numeric: "auto",
});

function parseDate(value) {
  if (!value) return null;

  const normalizedValue =
    typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}T/.test(value) &&
    !/(?:z|[+-]\d{2}:?\d{2})$/i.test(value)
      ? `${value}Z`
      : value;
  const date = new Date(normalizedValue);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatCreatedAt(value) {
  const date = parseDate(value);
  if (!date) return "Never";

  return date.toLocaleString(undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function formatRelativeTime(value, now) {
  const date = parseDate(value);
  if (!date) return "Never";

  const diffSeconds = Math.round((date.getTime() - now) / 1000);
  const absoluteSeconds = Math.abs(diffSeconds);

  if (absoluteSeconds < 60) {
    return relativeTimeFormatter.format(diffSeconds, "second");
  }

  const diffMinutes = Math.round(diffSeconds / 60);
  if (Math.abs(diffMinutes) < 60) {
    return relativeTimeFormatter.format(diffMinutes, "minute");
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) {
    return relativeTimeFormatter.format(diffHours, "hour");
  }

  const diffDays = Math.round(diffHours / 24);
  return relativeTimeFormatter.format(diffDays, "day");
}

const fileToImage = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const image = new Image();
      image.onload = () => resolve({ image, dataUrl: reader.result });
      image.onerror = () => reject(new Error("Failed to read profile picture"));
      image.src = reader.result;
    };
    reader.onerror = () => reject(new Error("Failed to read profile picture"));
    reader.readAsDataURL(file);
  });

const readProfilePictureFile = async (file) => {
  if (!file) return null;
  if (!ALLOWED_PROFILE_PICTURE_TYPES.has(file.type)) {
    throw new Error("Choose a PNG, JPG, or WebP image");
  }
  if (file.size > MAX_PROFILE_PICTURE_BYTES) {
    throw new Error("Profile picture must be 10 MB or smaller");
  }

  const { image, dataUrl } = await fileToImage(file);
  const maxSize = 512;
  const scale = Math.min(1, maxSize / Math.max(image.width, image.height));
  const width = Math.max(1, Math.round(image.width * scale));
  const height = Math.max(1, Math.round(image.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;

  const context = canvas.getContext("2d");
  if (!context) {
    return { data_url: dataUrl, filename: file.name };
  }

  context.drawImage(image, 0, 0, width, height);
  const outputType = file.type === "image/png" ? "image/png" : "image/jpeg";
  return {
    data_url: canvas.toDataURL(outputType, 0.86),
    filename: file.name,
    content_type: outputType,
  };
};

export default function Settings() {
  const auth = useAuth();
  const toast = useToast();
  const dispatch = useDispatch();
  const user = auth.user;
  const profilePictureInputRef = useRef(null);

  const [profileForm, setProfileForm] = useState({
    name: "",
    email: "",
    currentPassword: "",
  });
  const [passwordForm, setPasswordForm] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [profileEditing, setProfileEditing] = useState(false);
  const [passwordEditing, setPasswordEditing] = useState(false);
  const [profilePicturePayload, setProfilePicturePayload] = useState(null);
  const [profilePictureRemoved, setProfilePictureRemoved] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isSavingPassword, setIsSavingPassword] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [sessionPendingSignOut, setSessionPendingSignOut] = useState(null);

  useEffect(() => {
    setProfileForm({
      name: user?.name || "",
      email: user?.email || user?.username || "",
      currentPassword: "",
    });
    setProfilePicturePayload(null);
    setProfilePictureRemoved(false);
  }, [user?.email, user?.name, user?.profile_picture?.data_url, user?.username]);

  const loadSessions = async ({
    syncPublicIp = true,
    forcePublicIp = false,
    showPublicIpError = false,
  } = {}) => {
    setIsLoadingSessions(true);
    try {
      if (syncPublicIp) {
        const publicIpResult = await syncCurrentSessionPublicIp({
          username: user?.username,
          force: forcePublicIp,
          notify: false,
        });
        if (showPublicIpError && !publicIpResult?.ok) {
          toast.error(
            publicIpResult?.error ||
              "Could not update public IP. Public IP lookup may be blocked."
          );
        }
      }

      const response = await axios.get(apiRoutes.listSessions);
      setSessions(response?.data?.data || []);
    } catch (error) {
      toast.error(
        error?.response?.data?.detail || "Failed to load active sessions."
      );
    } finally {
      setIsLoadingSessions(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, [user?.username]);

  const initials = String(user?.name || user?.username || "A")
    .trim()
    .slice(0, 1)
    .toUpperCase();
  const savedProfilePictureSource = user?.profile_picture?.data_url || "";
  const profilePictureSource =
    profilePicturePayload?.data_url ||
    (!profilePictureRemoved ? savedProfilePictureSource : "");
  const emailChanged =
    profileForm.email.trim().toLowerCase() !==
    String(user?.email || user?.username || "")
      .trim()
      .toLowerCase();

  const handleProfilePictureChange = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    try {
      const nextPayload = await readProfilePictureFile(file);
      setProfilePicturePayload(nextPayload);
      setProfilePictureRemoved(false);
    } catch (error) {
      toast.error(error?.message || "Failed to read profile picture");
    }
  };

  const handleToggleProfileEditing = () => {
    setProfileEditing((editing) => {
      if (editing) {
        setProfilePicturePayload(null);
        setProfilePictureRemoved(false);
        setProfileForm({
          name: user?.name || "",
          email: user?.email || user?.username || "",
          currentPassword: "",
        });
      }
      return !editing;
    });
  };

  const handleSaveProfile = async () => {
    const name = profileForm.name.trim();
    const email = profileForm.email.trim().toLowerCase();

    if (!name || !email) {
      toast.error("Name and email are required.");
      return;
    }

    if (emailChanged && !profileForm.currentPassword) {
      toast.error("Current password is required to update email.");
      return;
    }

    setIsSavingProfile(true);
    try {
      const response = await axios.patch(apiRoutes.updateAccount, {
        name,
        email,
        current_password: emailChanged ? profileForm.currentPassword : null,
        profile_picture: profilePicturePayload,
        remove_profile_picture: profilePictureRemoved,
      });
      dispatch(authActions.setAccountInfo(response.data));
      setProfileForm((currentForm) => ({
        ...currentForm,
        currentPassword: "",
      }));
      setProfilePicturePayload(null);
      setProfilePictureRemoved(false);
      setProfileEditing(false);
      toast.success("Account updated.");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Failed to update account.");
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handleSavePassword = async () => {
    if (!passwordForm.currentPassword) {
      toast.error("Current password is required.");
      return;
    }
    if (passwordForm.newPassword.length < 8) {
      toast.error("Password must be at least 8 characters.");
      return;
    }
    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      toast.error("New passwords do not match.");
      return;
    }

    setIsSavingPassword(true);
    try {
      const response = await axios.patch(apiRoutes.updatePassword, {
        current_password: passwordForm.currentPassword,
        new_password: passwordForm.newPassword,
      });
      dispatch(
        authActions.updateAccountInfo({
          has_password: response?.data?.has_password ?? true,
        })
      );
      setPasswordForm({
        currentPassword: "",
        newPassword: "",
        confirmPassword: "",
      });
      setPasswordEditing(false);
      toast.success("Password updated.");
    } catch (error) {
      toast.error(
        error?.response?.data?.detail || "Failed to update password."
      );
    } finally {
      setIsSavingPassword(false);
    }
  };

  const confirmSessionSignOut = async () => {
    if (!sessionPendingSignOut) return;

    await handleRevokeSession(sessionPendingSignOut);
    setSessionPendingSignOut(null);
  };

  const handleRevokeSession = async (session) => {
    setActiveSessionId(session.id);
    try {
      await axios.delete(`${apiRoutes.revokeSession}/${session.id}`);
      if (session.current) {
        await auth.signOut({ redirect: true });
        return;
      }

      setSessions((currentSessions) =>
        currentSessions.filter(
          (currentSession) => currentSession.id !== session.id
        )
      );
      toast.success("Session signed out.");
    } catch (error) {
      toast.error(
        error?.response?.data?.detail || "Failed to sign out session."
      );
    } finally {
      setActiveSessionId(null);
    }
  };

  return (
    <div className="min-h-full bg-neutral-50 px-3 py-4 dark:bg-[#18191b] md:px-6 md:py-6">
      <div className="mx-auto max-w-5xl space-y-4">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">
            Settings
          </h1>
          <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
            Manage your account profile and password.
          </p>
        </div>

        <section className={settingsPanelClass}>
          <div
            className={`flex flex-wrap items-center justify-between gap-4 border-b px-5 py-4 ${settingsDividerClass}`}
          >
            <div className="flex min-w-0 items-center gap-3">
              {profilePictureSource ? (
                <img
                  src={profilePictureSource}
                  alt="Profile"
                  className="h-12 w-12 shrink-0 rounded-md object-cover"
                />
              ) : (
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md bg-blue-600 text-base font-semibold text-white dark:bg-blue-700">
                  {initials}
                </div>
              )}
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                  {user?.name || "Account"}
                </p>
                <p className="mt-0.5 truncate text-sm text-neutral-500 dark:text-neutral-400">
                  {user?.email || user?.username || "Signed in user"}
                </p>
              </div>
            </div>
            <button
              type="button"
              className="rounded-md border border-neutral-300 px-3 py-2 text-sm font-medium text-neutral-700 transition hover:bg-neutral-100 dark:border-[#33363b] dark:text-neutral-200 dark:hover:bg-[#2a2b2f]"
              onClick={handleToggleProfileEditing}
            >
              {profileEditing ? "Cancel" : "Edit"}
            </button>
          </div>

          {!profileEditing ? (
            <div className="divide-y divide-neutral-100 px-5 dark:divide-[#33363b]">
              <div className="flex items-center justify-between gap-4 py-3">
                <span className="text-sm text-neutral-500 dark:text-neutral-400">
                  Name
                </span>
                <span className="min-w-0 truncate text-right text-sm font-medium text-neutral-900 dark:text-neutral-100">
                  {user?.name || "Not available"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4 py-3">
                <span className="text-sm text-neutral-500 dark:text-neutral-400">
                  Email
                </span>
                <span className="min-w-0 truncate text-right text-sm font-medium text-neutral-900 dark:text-neutral-100">
                  {user?.email || user?.username || "Not available"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4 py-3">
                <span className="text-sm text-neutral-500 dark:text-neutral-400">
                  Member since
                </span>
                <span className="min-w-0 truncate text-right text-sm font-medium text-neutral-900 dark:text-neutral-100">
                  {formatCreatedAt(user?.created_at)}
                </span>
              </div>
            </div>
          ) : (
            <div className="space-y-3 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-neutral-50 p-3 dark:bg-[#18191b]">
                <div className="flex min-w-0 items-center gap-3">
                  {profilePictureSource ? (
                    <img
                      src={profilePictureSource}
                      alt="Profile preview"
                      className="h-12 w-12 shrink-0 rounded-md object-cover"
                    />
                  ) : (
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md bg-blue-600 text-base font-semibold text-white dark:bg-blue-700">
                      {initials}
                    </div>
                  )}
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                      Profile picture
                    </p>
                    <p className="mt-0.5 text-xs text-neutral-500 dark:text-neutral-400">
                      PNG, JPG, or WebP. Optimized before saving.
                    </p>
                  </div>
                </div>
                <input
                  ref={profilePictureInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="hidden"
                  onChange={handleProfilePictureChange}
                />
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 rounded-md border border-neutral-300 px-3 py-2 text-sm font-medium text-neutral-700 transition hover:bg-neutral-100 dark:border-[#33363b] dark:text-neutral-200 dark:hover:bg-[#2a2b2f]"
                    onClick={() => profilePictureInputRef.current?.click()}
                  >
                    <FiUpload size={14} />
                    {profilePictureSource ? "Change" : "Upload"}
                  </button>
                  {profilePictureSource ? (
                    <button
                      type="button"
                      className="inline-flex items-center gap-2 rounded-md border border-red-300 px-3 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50 dark:border-red-900/70 dark:text-red-300 dark:hover:bg-red-950/30"
                      onClick={() => {
                        setProfilePicturePayload(null);
                        setProfilePictureRemoved(true);
                      }}
                    >
                      <FiTrash2 size={14} />
                      Remove
                    </button>
                  ) : null}
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <label className="block">
                  <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
                    Name
                  </span>
                  <input
                    className={accountInputClass}
                    value={profileForm.name}
                    onChange={(event) =>
                      setProfileForm((currentForm) => ({
                        ...currentForm,
                        name: event.target.value,
                      }))
                    }
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
                    Email
                  </span>
                  <input
                    type="email"
                    className={accountInputClass}
                    value={profileForm.email}
                    onChange={(event) =>
                      setProfileForm((currentForm) => ({
                        ...currentForm,
                        email: event.target.value,
                      }))
                    }
                  />
                </label>
              </div>

              {emailChanged ? (
                <label className="block">
                  <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
                    Current password for email changes
                  </span>
                  <input
                    type="password"
                    className={accountInputClass}
                    value={profileForm.currentPassword}
                    onChange={(event) =>
                      setProfileForm((currentForm) => ({
                        ...currentForm,
                        currentPassword: event.target.value,
                      }))
                    }
                  />
                </label>
              ) : null}

              <div className="flex items-center justify-between gap-4 border-t border-neutral-100 pt-4 dark:border-[#33363b]">
                <p className="text-sm text-neutral-500 dark:text-neutral-400">
                  Member since {formatCreatedAt(user?.created_at)}
                </p>
                <button
                  type="button"
                  className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={handleSaveProfile}
                  disabled={isSavingProfile}
                >
                  {isSavingProfile ? "Saving..." : "Save changes"}
                </button>
              </div>
            </div>
          )}
        </section>

        <section className={settingsPanelClass}>
          <div
            className={`flex items-center justify-between gap-4 border-b px-5 py-4 ${settingsDividerClass}`}
          >
            <div>
              <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                Password
              </p>
              <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
                Change your password using your current password.
              </p>
            </div>
            <button
              type="button"
              className="shrink-0 whitespace-nowrap rounded-md border border-neutral-300 px-3 py-2 text-sm font-medium text-neutral-700 transition hover:bg-neutral-100 dark:border-[#33363b] dark:text-neutral-200 dark:hover:bg-[#2a2b2f]"
              onClick={() => setPasswordEditing((editing) => !editing)}
            >
              {passwordEditing ? "Cancel" : "Change password"}
            </button>
          </div>

          {passwordEditing ? (
            <div className="space-y-3 p-5">
              <input
                type="password"
                placeholder="Current password"
                className={accountInputClass}
                value={passwordForm.currentPassword}
                onChange={(event) =>
                  setPasswordForm((currentForm) => ({
                    ...currentForm,
                    currentPassword: event.target.value,
                  }))
                }
              />
              <input
                type="password"
                placeholder="New password"
                className={accountInputClass}
                value={passwordForm.newPassword}
                onChange={(event) =>
                  setPasswordForm((currentForm) => ({
                    ...currentForm,
                    newPassword: event.target.value,
                  }))
                }
              />
              <input
                type="password"
                placeholder="Confirm new password"
                className={accountInputClass}
                value={passwordForm.confirmPassword}
                onChange={(event) =>
                  setPasswordForm((currentForm) => ({
                    ...currentForm,
                    confirmPassword: event.target.value,
                  }))
                }
              />
              <button
                type="button"
                className="whitespace-nowrap rounded-md border border-neutral-300 px-3 py-2 text-sm font-medium text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-[#33363b] dark:text-neutral-200 dark:hover:bg-[#2a2b2f]"
                onClick={handleSavePassword}
                disabled={isSavingPassword}
              >
                {isSavingPassword ? "Updating..." : "Update password"}
              </button>
            </div>
          ) : (
            <div className="px-5 py-4 text-sm text-neutral-500 dark:text-neutral-400">
              Password changes are hidden until you choose to update them.
            </div>
          )}
        </section>

        <section className={settingsPanelClass}>
          <div
            className={`flex items-center justify-between gap-4 border-b px-5 py-4 ${settingsDividerClass}`}
          >
            <div>
              <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                Active sessions
              </p>
              <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
                Review devices that are signed in and revoke access when needed.
              </p>
            </div>
            <button
              type="button"
              className="inline-flex shrink-0 items-center gap-2 rounded-md border border-neutral-300 px-3 py-2 text-sm font-medium text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-[#33363b] dark:text-neutral-200 dark:hover:bg-[#2a2b2f]"
              onClick={() =>
                loadSessions({
                  forcePublicIp: true,
                  showPublicIpError: true,
                })
              }
              disabled={isLoadingSessions}
            >
              <FiRefreshCw size={14} />
              Refresh
            </button>
          </div>
          <div className="divide-y divide-neutral-100 dark:divide-[#33363b]">
            {isLoadingSessions ? (
              <div className="px-5 py-6 text-sm text-neutral-500 dark:text-neutral-400">
                Loading sessions...
              </div>
            ) : sessions.length ? (
              sessions.map((session) => (
                <div
                  key={session.id}
                  className="flex items-center justify-between gap-4 px-5 py-4"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-medium text-neutral-900 dark:text-neutral-100">
                        {session.device_name}
                      </p>
                      {session.current ? (
                        <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-300">
                          Current
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
                      {session.ip || "Unknown IP"} · Last active{" "}
                      {formatRelativeTime(session.last_accessed_at, Date.now())}
                    </p>
                    <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-500">
                      Created {formatCreatedAt(session.created_at)}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="inline-flex shrink-0 items-center gap-2 rounded-md border border-neutral-300 px-3 py-2 text-sm font-medium text-neutral-700 transition hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-[#33363b] dark:text-neutral-200 dark:hover:bg-[#2a2b2f]"
                    onClick={() => setSessionPendingSignOut(session)}
                    disabled={activeSessionId === session.id}
                  >
                    <FaSignOutAlt size={14} />
                    {activeSessionId === session.id
                      ? "Signing out..."
                      : "Sign out"}
                  </button>
                </div>
              ))
            ) : (
              <div className="px-5 py-6 text-sm text-neutral-500 dark:text-neutral-400">
                No active sessions found.
              </div>
            )}
          </div>
        </section>
      </div>

      {sessionPendingSignOut ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 backdrop-blur-[1px]">
          <div className="w-full max-w-sm rounded-lg border border-neutral-200 bg-white p-4 shadow-lg dark:border-[#33363b] dark:bg-[#202124]">
            <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
              {sessionPendingSignOut.current
                ? "Sign out current session?"
                : "Sign out this session?"}
            </p>
            <p className="mt-2 text-sm leading-6 text-neutral-500 dark:text-neutral-400">
              {sessionPendingSignOut.current
                ? "You will be signed out of this browser."
                : "That device will need to sign in again."}
            </p>
            <div className="mt-4 rounded-md bg-neutral-50 px-3 py-2 dark:bg-[#18191b]">
              <p className="truncate text-sm font-medium text-neutral-900 dark:text-neutral-100">
                {sessionPendingSignOut.device_name}
              </p>
              <p className="mt-1 truncate text-xs text-neutral-500 dark:text-neutral-400">
                {sessionPendingSignOut.ip || "Unknown IP"}
              </p>
            </div>
            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                type="button"
                className="rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-600 transition-colors hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-[#33363b] dark:text-neutral-300 dark:hover:bg-[#2a2b2f]"
                onClick={() => setSessionPendingSignOut(null)}
                disabled={activeSessionId === sessionPendingSignOut.id}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-md bg-red-500 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-red-600 dark:hover:bg-red-500"
                onClick={confirmSessionSignOut}
                disabled={activeSessionId === sessionPendingSignOut.id}
              >
                {activeSessionId === sessionPendingSignOut.id
                  ? "Signing out..."
                  : "Sign out"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
