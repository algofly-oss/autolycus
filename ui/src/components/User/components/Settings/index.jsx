import {useRouter} from "next/router";
import { IconUser, IconUsers, IconFileText, IconShieldLock, IconFolder, IconLink, IconDevices } from "@tabler/icons-react";
import SubtitleConnection from "@/shared/SubtitleConnection";
import { ProfileSettings } from "@/shared/MediaProfiles";
import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { useDispatch } from "react-redux";
import { FiCopy, FiEdit3, FiRefreshCw, FiTrash2, FiUpload, FiSearch } from "react-icons/fi";
import { FaSignOutAlt } from "react-icons/fa";
import { AiOutlineEye, AiOutlineEyeInvisible } from "react-icons/ai";
import apiRoutes from "@/shared/routes/apiRoutes";
import { syncCurrentSessionPublicIp } from "@/shared/sessionPublicIp";
import useAuth from "@/shared/hooks/useAuth";
import useToast from "@/shared/hooks/useToast";
import { authActions } from "@/redux/features/authSlice";
import {
  CLIPBOARD_COPY_STATUS,
  copyTextToClipboard,
} from "@/shared/utils/clipboard";

const settingsPanelClass =
  "min-w-0";
const accountInputClass = "settings-input";
const passwordInputClass = `${accountInputClass} pr-10`;
const passwordToggleClass = "settings-password-toggle";
const publicUrlDeleteButtonClass = "settings-button settings-button-danger public-url-delete-button";
const PUBLIC_URL_PAGE_SIZE = 10;
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
  const [passwordVisibility, setPasswordVisibility] = useState({
    profileCurrent: false,
    accountCurrent: false,
    accountNew: false,
    accountConfirm: false,
    ftp: false,
  });
  const [profilePicturePayload, setProfilePicturePayload] = useState(null);
  const [profilePictureRemoved, setProfilePictureRemoved] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isSavingPassword, setIsSavingPassword] = useState(false);
  const [sessions, setSessions] = useState([]);
  const router=useRouter();
  const [settingsCategory, setSettingsCategory] = useState("account");
  useEffect(()=>{
    if(["account","profiles","subtitles","security","ftp","links","sessions"].includes(router.query.category))setSettingsCategory(router.query.category);
  },[router.query.category]);
  const [sessionQuery, setSessionQuery] = useState("");
  const [sessionFilter, setSessionFilter] = useState("all");
  const [sessionPage, setSessionPage] = useState(1);
  const [sessionTotal, setSessionTotal] = useState(0);
  const [filteredSessionCount, setFilteredSessionCount] = useState(0);
  const sessionRequest = useRef(0);
  const sessionPageCount = Math.max(1,Math.ceil(filteredSessionCount/10));
  const visibleSessions = sessions;
  useEffect(() => setSessionPage(1), [sessionQuery,sessionFilter]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [sessionPendingSignOut, setSessionPendingSignOut] = useState(null);
  const [ftpSettings, setFtpSettings] = useState({
    enabled: false,
    username: "",
    has_password: false,
    password: "",
    friendly_names: false,
    url: "",
  });
  const [ftpForm, setFtpForm] = useState({
    enabled: false,
    username: "",
    password: "",
    friendly_names: false,
  });
  const [isLoadingFtp, setIsLoadingFtp] = useState(true);
  const [isSavingFtp, setIsSavingFtp] = useState(false);
  const [ftpEditing, setFtpEditing] = useState(false);
  const [publicUrls, setPublicUrls] = useState([]);
  const [publicUrlsPage, setPublicUrlsPage] = useState(1);
  const [publicUrlsTotal, setPublicUrlsTotal] = useState(0);
  const [selectedPublicUrlHashes, setSelectedPublicUrlHashes] = useState([]);
  const [isLoadingPublicUrls, setIsLoadingPublicUrls] = useState(true);
  const [deactivatingPublicUrl, setDeactivatingPublicUrl] = useState("");
  const [confirmDeleteAllPublicUrls, setConfirmDeleteAllPublicUrls] =
    useState(false);

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
    const requestId=++sessionRequest.current;
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

      const response = await axios.get(apiRoutes.listSessions, {params:{page:sessionPage,page_size:10,query:sessionQuery,device_filter:sessionFilter}});
      if(requestId!==sessionRequest.current)return;
      setSessions(response?.data?.data || []);
      setSessionTotal(response.data.meta?.all_total || 0);
      setFilteredSessionCount(response.data.meta?.total || 0);
      setSessionPage(page=>Math.min(page,Math.max(1,Math.ceil((response.data.meta?.total || 0)/10))));
    } catch (error) {
      toast.error(
        error?.response?.data?.detail || "Failed to load active sessions."
      );
    } finally {
      if(requestId===sessionRequest.current)setIsLoadingSessions(false);
    }
  };

  useEffect(() => {
    const timer=setTimeout(()=>loadSessions({syncPublicIp:!sessionQuery&&sessionFilter==="all"&&sessionPage===1}),150);
    return ()=>clearTimeout(timer);
  }, [user?.username,sessionQuery,sessionFilter,sessionPage]);

  const loadFtpSettings = async () => {
    setIsLoadingFtp(true);
    try {
      const response = await axios.get(apiRoutes.ftpSettings);
      const nextSettings = response?.data?.ftp || {};
      setFtpSettings(nextSettings);
      setFtpForm({
        enabled: Boolean(nextSettings.enabled),
        username: nextSettings.username || "",
        password: nextSettings.password || "",
        friendly_names: Boolean(nextSettings.friendly_names),
      });
      setFtpEditing(false);
    } catch (error) {
      toast.error(
        error?.response?.data?.detail || "Failed to load FTP settings."
      );
    } finally {
      setIsLoadingFtp(false);
    }
  };

  useEffect(() => {
    loadFtpSettings();
  }, [user?.username]);

  const publicUrlsTotalPages = Math.max(
    1,
    Math.ceil((publicUrlsTotal || 0) / PUBLIC_URL_PAGE_SIZE)
  );
  const publicUrlPageNumbers = (() => {
    if (publicUrlsTotalPages <= 1) return [];

    const visiblePages = new Set([1, publicUrlsTotalPages]);
    const startPage = Math.max(1, publicUrlsPage - 2);
    const endPage = Math.min(publicUrlsTotalPages, publicUrlsPage + 2);

    for (let page = startPage; page <= endPage; page += 1) {
      visiblePages.add(page);
    }

    return Array.from(visiblePages)
      .sort((firstPage, secondPage) => firstPage - secondPage)
      .reduce((pages, page) => {
        const previousPage = pages[pages.length - 1];
        if (typeof previousPage === "number" && page - previousPage > 1) {
          pages.push(`ellipsis-${previousPage}-${page}`);
        }
        pages.push(page);
        return pages;
      }, []);
  })();

  const loadPublicUrls = async (page = publicUrlsPage) => {
    setIsLoadingPublicUrls(true);
    try {
      const response = await axios.get(apiRoutes.listPublicUrls, {
        params: { page, page_size: PUBLIC_URL_PAGE_SIZE },
      });
      const nextUrls = response?.data?.data || [];
      const meta = response?.data?.meta || {};
      const total = Number(meta.total || 0);
      const totalPages = Math.max(1, Math.ceil(total / PUBLIC_URL_PAGE_SIZE));
      if (page > totalPages) {
        setPublicUrlsPage(totalPages);
        return;
      }
      setPublicUrls(nextUrls);
      setPublicUrlsTotal(total);
      setSelectedPublicUrlHashes((currentHashes) =>
        currentHashes.filter((hash) =>
          nextUrls.some((item) => item.path_hash === hash)
        )
      );
    } catch (error) {
      toast.error(
        error?.response?.data?.detail || "Failed to load public URLs."
      );
    } finally {
      setIsLoadingPublicUrls(false);
    }
  };

  useEffect(() => {
    loadPublicUrls(publicUrlsPage);
  }, [user?.username, publicUrlsPage]);

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

  const resetProfileForm = () => {
    setProfilePicturePayload(null);
    setProfilePictureRemoved(false);
    setProfileForm({name:user?.name || "",email:user?.email || user?.username || "",currentPassword:""});
  };

  const togglePasswordVisibility = (key) => {
    setPasswordVisibility((currentVisibility) => ({
      ...currentVisibility,
      [key]: !currentVisibility[key],
    }));
  };

  const renderPasswordToggle = (key, isVisible) => (
    <button
      type="button"
      className={passwordToggleClass}
      onClick={() => togglePasswordVisibility(key)}
      aria-label={isVisible ? "Hide password" : "Show password"}
      title={isVisible ? "Hide password" : "Show password"}
    >
      {isVisible ? (
        <AiOutlineEyeInvisible size={18} />
      ) : (
        <AiOutlineEye size={18} />
      )}
    </button>
  );

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
      toast.success("Password updated.");
    } catch (error) {
      toast.error(
        error?.response?.data?.detail || "Failed to update password."
      );
    } finally {
      setIsSavingPassword(false);
    }
  };

  const resetFtpForm = (settings = ftpSettings) => {
    setFtpForm({
      enabled: Boolean(settings.enabled),
      username: settings.username || "",
      password: settings.password || "",
      friendly_names: Boolean(settings.friendly_names),
    });
  };

  const openFtpEditor = () => {
    setFtpEditing(true);
    setFtpForm({
      enabled: Boolean(ftpSettings.enabled),
      username: ftpSettings.username || "",
      password: ftpSettings.password || "",
      friendly_names: Boolean(ftpSettings.friendly_names),
    });
  };

  const cancelFtpEditor = () => {
    resetFtpForm();
    setFtpEditing(false);
  };

  const persistFtpSettings = async ({
    enabled,
    username,
    password,
    friendly_names,
  }) => {
    setIsSavingFtp(true);
    try {
      const response = await axios.patch(apiRoutes.ftpSettings, {
        enabled,
        username,
        password,
        friendly_names,
      });
      const nextSettings = response?.data?.ftp || {};
      setFtpSettings(nextSettings);
      setFtpForm({
        enabled: Boolean(nextSettings.enabled),
        username: nextSettings.username || "",
        password: nextSettings.password || "",
        friendly_names: Boolean(nextSettings.friendly_names),
      });
      setFtpEditing(false);
      if (response?.data?.preferences) {
        dispatch(
          authActions.updateAccountInfo({
            preferences: response.data.preferences,
          })
        );
      }
      toast.success("FTP settings updated.");
    } catch (error) {
      toast.error(
        error?.response?.data?.detail || "Failed to update FTP settings."
      );
    } finally {
      setIsSavingFtp(false);
    }
  };

  const handleSaveFtpSettings = () => {
    const nextUsername = ftpForm.username.trim();
    const nextPassword = ftpForm.password;

    if (ftpForm.enabled && !nextUsername) {
      toast.error("FTP username is required.");
      return;
    }

    if (ftpForm.enabled && !ftpSettings.has_password && !nextPassword) {
      toast.error("FTP password is required the first time you enable FTP.");
      return;
    }

    if (nextPassword && nextPassword.length < 8) {
      toast.error("FTP password must be at least 8 characters.");
      return;
    }

    const payload = {
      enabled: ftpForm.enabled,
      username: nextUsername,
      password: nextPassword,
      friendly_names: ftpForm.friendly_names,
    };

    persistFtpSettings(payload);
  };

  const handleCopyFtpUrl = async () => {
    if (!ftpSettings?.url) {
      toast.error("FTP URL is not available.");
      return;
    }

    const status = await copyTextToClipboard(ftpSettings.url);
    if (status === CLIPBOARD_COPY_STATUS.COPIED) {
      toast.success("FTP URL copied to clipboard");
    } else if (status === CLIPBOARD_COPY_STATUS.MANUAL) {
      toast.success("FTP URL opened for manual copy");
    } else {
      toast.error("Failed to copy FTP URL");
    }
  };

  const publicUrlForKey = (key) => {
    if (!key || typeof window === "undefined") return "";
    return `${window.location.origin}/watch?key=${encodeURIComponent(key)}`;
  };

  const handleCopyPublicUrl = async (item) => {
    const url = publicUrlForKey(item?.key);
    if (!url) {
      toast.error("Public URL is not available.");
      return;
    }

    const status = await copyTextToClipboard(url);
    if (status === CLIPBOARD_COPY_STATUS.COPIED) {
      toast.success("Public URL copied to clipboard");
    } else if (status === CLIPBOARD_COPY_STATUS.MANUAL) {
      toast.success("Public URL opened for manual copy");
    } else {
      toast.error("Failed to copy public URL");
    }
  };

  const handleDeactivatePublicUrl = async (item) => {
    if (!item?.path_hash) return;

    setDeactivatingPublicUrl(item.path_hash);
    try {
      await axios.patch(
        `${apiRoutes.deactivatePublicUrl}/${encodeURIComponent(
          item.path_hash
        )}/deactivate`
      );
      setPublicUrls((currentUrls) =>
        currentUrls.filter((url) => url.path_hash !== item.path_hash)
      );
      setSelectedPublicUrlHashes((currentHashes) =>
        currentHashes.filter((hash) => hash !== item.path_hash)
      );
      setPublicUrlsTotal((currentTotal) => Math.max(0, currentTotal - 1));
      toast.success("Public URL deleted.");
    } catch (error) {
      toast.error(
        error?.response?.data?.detail || "Failed to delete public URL."
      );
    } finally {
      setDeactivatingPublicUrl("");
    }
  };

  const togglePublicUrlSelection = (pathHash) => {
    setSelectedPublicUrlHashes((currentHashes) =>
      currentHashes.includes(pathHash)
        ? currentHashes.filter((hash) => hash !== pathHash)
        : [...currentHashes, pathHash]
    );
  };

  const handleBulkDeletePublicUrls = async ({ all = false } = {}) => {
    if (!all && selectedPublicUrlHashes.length === 0) {
      toast.error("Select at least one public URL.");
      return;
    }

    setDeactivatingPublicUrl(all ? "__all__" : "__selected__");
    try {
      await axios.patch(apiRoutes.bulkDeactivatePublicUrls, {
        all,
        path_hashes: all ? [] : selectedPublicUrlHashes,
      });
      setSelectedPublicUrlHashes([]);
      if (all) {
        setPublicUrls([]);
        setPublicUrlsTotal(0);
        setPublicUrlsPage(1);
        setConfirmDeleteAllPublicUrls(false);
      } else {
        await loadPublicUrls(publicUrlsPage);
      }
      toast.success(all ? "All public URLs deleted." : "Selected public URLs deleted.");
    } catch (error) {
      toast.error(
        error?.response?.data?.detail || "Failed to delete public URLs."
      );
    } finally {
      setDeactivatingPublicUrl("");
    }
  };

  const confirmSessionSignOut = async () => {
    if (!sessionPendingSignOut) return;

    await handleRevokeSession(sessionPendingSignOut);
    setSessionPendingSignOut(null);
  };

  const renderPublicUrlsSection = () => (
    <section className={settingsPanelClass}>
      <div
        className="settings-section-heading"
      >
        <div>
          <p className="text-sm font-semibold settings-foreground">
            Public URLs
          </p>
          <p className="mt-1 text-sm settings-secondary">
            Manage active public file links.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
          {publicUrlsTotal > 0 ? (
            <button
              type="button"
              className={publicUrlDeleteButtonClass}
              onClick={() =>
                selectedPublicUrlHashes.length > 0
                  ? handleBulkDeletePublicUrls()
                  : setConfirmDeleteAllPublicUrls(true)
              }
              disabled={Boolean(deactivatingPublicUrl)}
            >
              {deactivatingPublicUrl === "__selected__"
                ? "Deleting..."
                : deactivatingPublicUrl === "__all__"
                ? "Deleting..."
                : selectedPublicUrlHashes.length > 0
                ? `Delete selected (${selectedPublicUrlHashes.length})`
                : "Delete all"}
            </button>
          ) : null}
          <button
            type="button"
            className="settings-button"
            onClick={() => loadPublicUrls(publicUrlsPage)}
            disabled={isLoadingPublicUrls}
          >
            <FiRefreshCw size={14} />
            Refresh
          </button>
        </div>
      </div>
      <div className="settings-divided-list">
        {isLoadingPublicUrls ? (
          <div className="px-5 py-6 text-sm settings-secondary">
            Loading public URLs...
          </div>
        ) : publicUrls.length ? (
          <>
            {publicUrls.map((item) => {
              const publicUrl = publicUrlForKey(item.key);
              const isDeactivating = deactivatingPublicUrl === item.path_hash;
              const isSelected = selectedPublicUrlHashes.includes(item.path_hash);

              return (
                <div
                  key={item.path_hash}
                  className="settings-device-row"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <input
                      type="checkbox"
                      className="h-4 w-4 shrink-0 rounded border-neutral-300 text-blue-600 focus:ring-blue-500 settings-border dark:bg-[#18191b]"
                      checked={isSelected}
                      onChange={() => togglePublicUrlSelection(item.path_hash)}
                    />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium settings-foreground">
                        {item.name || item.key}
                      </p>
                      <p className="mt-1 truncate text-xs settings-secondary">
                        {publicUrl}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 sm:shrink-0">
                    <button
                      type="button"
                      className="settings-button"
                      onClick={() => handleCopyPublicUrl(item)}
                    >
                      <FiCopy size={14} />
                      Copy
                    </button>
                    <button
                      type="button"
                      className={publicUrlDeleteButtonClass}
                      onClick={() => handleDeactivatePublicUrl(item)}
                      disabled={isDeactivating || Boolean(deactivatingPublicUrl)}
                    >
                      {isDeactivating ? "Deleting..." : "Delete"}
                    </button>
                  </div>
                </div>
              );
            })}
            <div className="settings-pagination">
              <p className="text-xs settings-secondary">
                Page {publicUrlsPage} of {publicUrlsTotalPages}
              </p>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <button
                  type="button"
                  className="settings-button"
                  onClick={() =>
                    setPublicUrlsPage((currentPage) =>
                      Math.max(1, currentPage - 1)
                    )
                  }
                  disabled={publicUrlsPage <= 1 || isLoadingPublicUrls}
                >
                  Previous
                </button>
                {publicUrlPageNumbers.map((page) =>
                  typeof page === "number" ? (
                    <button
                      key={page}
                      type="button"
                      className={`min-w-[2.25rem] rounded-md border px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${
                        page === publicUrlsPage
                          ? "border-blue-500 bg-blue-600 text-white dark:border-blue-500 dark:bg-blue-500 dark:text-white"
                          : "border-neutral-300 text-neutral-700 hover:bg-neutral-100 settings-border dark:text-neutral-200 dark:hover:bg-[#2a2b2f]"
                      }`}
                      onClick={() => setPublicUrlsPage(page)}
                      disabled={page === publicUrlsPage || isLoadingPublicUrls}
                    >
                      {page}
                    </button>
                  ) : (
                    <span
                      key={page}
                      className="px-1 text-sm text-neutral-400 dark:settings-secondary"
                    >
                      ...
                    </span>
                  )
                )}
                <button
                  type="button"
                  className="settings-button"
                  onClick={() =>
                    setPublicUrlsPage((currentPage) =>
                      Math.min(publicUrlsTotalPages, currentPage + 1)
                    )
                  }
                  disabled={
                    publicUrlsPage >= publicUrlsTotalPages || isLoadingPublicUrls
                  }
                >
                  Next
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="px-5 py-6 text-sm settings-secondary">
            No active public URLs.
          </div>
        )}
      </div>
    </section>
  );

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
      loadSessions({syncPublicIp:false});
    } catch (error) {
      toast.error(
        error?.response?.data?.detail || "Failed to sign out session."
      );
    } finally {
      setActiveSessionId(null);
    }
  };

  return (
    <div className="porthub-settings">
      <div className="settings-workspace">
        <header className="settings-heading"><h1>Settings</h1></header>
        <div className="settings-layout">
          <nav aria-label="Settings categories" className="settings-category-nav">
            {[
              ["account","Account","Account details",IconUser],
              ["profiles","Profiles","Identity & watch history",IconUsers],
              ["subtitles","Subtitles","Languages & connection",IconFileText],
              ["security","Security","Password & protection",IconShieldLock],
              ["ftp","FTP sharing","File access",IconFolder],
              ["links","Public links","Manage shared files",IconLink],
              ["sessions","Sessions","Signed-in devices",IconDevices],
            ].map(([key,label,description,Icon]) => <button key={key} type="button" aria-label={label} aria-pressed={settingsCategory===key} aria-current={settingsCategory===key?"page":undefined} onClick={()=>{setSettingsCategory(key);router.replace({pathname:router.pathname,query:{...router.query,category:key}},undefined,{shallow:true,scroll:false});}}>
              <Icon size={18}/><span><span className="settings-nav-label">{label}</span><span className="settings-nav-description">{description}</span></span>
            </button>)}
          </nav>
          <div className="settings-content">
        <div hidden={settingsCategory!=="subtitles"}><SubtitleConnection /></div>
        <div hidden={settingsCategory!=="profiles"}><ProfileSettings /></div>
        <section hidden={settingsCategory!=="account"} className={settingsPanelClass}>
          <div className="settings-intro"><h2>Account</h2><p>Manage your account identity and contact information.</p></div>
          <div className="settings-row"><div><h3>Profile Photo</h3><p>PNG, JPG, or WebP. Maximum 10 MB.</p></div><div><div className="flex flex-wrap items-center gap-4 ">
                <div className="flex min-w-0 items-center gap-3">
                  {profilePictureSource ? (
                    <img
                      src={profilePictureSource}
                      alt="Profile preview"
                      className="h-14 w-14 shrink-0 rounded-full object-cover"
                    />
                  ) : (
                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-blue-600 text-base font-semibold text-white dark:bg-blue-700">
                      {initials}
                    </div>
                  )}

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
                    className="settings-button"
                    onClick={() => profilePictureInputRef.current?.click()}
                  >
                    <FiUpload size={14} />
                    Upload Photo
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
              </div></div></div>
          <div className="settings-row"><div><h3>Account Details</h3><p>Your name and email address.</p></div><div><div className="space-y-5">
                <label className="block">
                  <span className="text-sm font-medium">
                    Display name
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
                  <span className="text-sm font-medium">
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
              </div></div></div>
          {emailChanged ? (
                <label className="block">
                  <span className="text-xs font-medium settings-secondary">
                    Current password for email changes
                  </span>
                  <div className="relative">
                    <input
                      type={
                        passwordVisibility.profileCurrent ? "text" : "password"
                      }
                      className={passwordInputClass}
                      value={profileForm.currentPassword}
                      onChange={(event) =>
                        setProfileForm((currentForm) => ({
                          ...currentForm,
                          currentPassword: event.target.value,
                        }))
                      }
                    />
                    {renderPasswordToggle(
                      "profileCurrent",
                      passwordVisibility.profileCurrent
                    )}
                  </div>
                </label>
              ) : null}
          <div className="settings-form-footer">
            <button type="button" className="rounded-md px-3 py-2 text-sm" onClick={()=>{resetProfileForm();}}>Discard Changes</button>
            <button type="button" className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50" onClick={handleSaveProfile} disabled={isSavingProfile}>{isSavingProfile?"Saving…":"Save Profile"}</button>
          </div>
        </section>

        <section hidden={settingsCategory!=="security"} className={settingsPanelClass}>
          <div className="settings-intro"><h2>Security</h2><p>Manage your password and protect your account.</p></div>
          <div className="settings-row"><div><h3>Change Password</h3><p>Use your current password to set a new one.</p></div>
            <div className="space-y-5">
              <div className="relative">
                <input
                  type={passwordVisibility.accountCurrent ? "text" : "password"}
                  placeholder="Current password"
                  className={passwordInputClass}
                  value={passwordForm.currentPassword}
                  onChange={(event) =>
                    setPasswordForm((currentForm) => ({
                      ...currentForm,
                      currentPassword: event.target.value,
                    }))
                  }
                />
                {renderPasswordToggle(
                  "accountCurrent",
                  passwordVisibility.accountCurrent
                )}
              </div>
              <div className="relative">
                <input
                  type={passwordVisibility.accountNew ? "text" : "password"}
                  placeholder="New password"
                  className={passwordInputClass}
                  value={passwordForm.newPassword}
                  onChange={(event) =>
                    setPasswordForm((currentForm) => ({
                      ...currentForm,
                      newPassword: event.target.value,
                    }))
                  }
                />
                {renderPasswordToggle(
                  "accountNew",
                  passwordVisibility.accountNew
                )}
              </div>
              <div className="relative">
                <input
                  type={passwordVisibility.accountConfirm ? "text" : "password"}
                  placeholder="Confirm new password"
                  className={passwordInputClass}
                  value={passwordForm.confirmPassword}
                  onChange={(event) =>
                    setPasswordForm((currentForm) => ({
                      ...currentForm,
                      confirmPassword: event.target.value,
                    }))
                  }
                />
                {renderPasswordToggle(
                  "accountConfirm",
                  passwordVisibility.accountConfirm
                )}
              </div>
              <button
                type="button"
                className="settings-button"
                onClick={handleSavePassword}
                disabled={isSavingPassword}
              >
                {isSavingPassword ? "Updating..." : "Update password"}
              </button>
            </div>
          </div>
        </section>

        <section hidden={settingsCategory!=="ftp"} className={settingsPanelClass}>
          <div
            className="settings-section-heading"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold settings-foreground">
                  FTP share
                </p>
                {!isLoadingFtp ? (
                  <span
                    className={`shrink-0 rounded-md px-2 py-0.5 text-[11px] font-semibold ${
                      ftpSettings.enabled
                        ? "bg-emerald-500/15 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300"
                        : "bg-neutral-200 text-neutral-600 dark:bg-[#2a2b2f] dark:text-neutral-300"
                    }`}
                  >
                    {ftpSettings.enabled ? "Enabled" : "Disabled"}
                  </span>
                ) : null}
              </div>
              <p className="mt-1 text-sm settings-secondary">
                Enable FTP access to your downloads.
              </p>
            </div>
            <div className="flex items-center sm:shrink-0">
              <button
                type="button"
                className="settings-button"
                onClick={ftpEditing ? cancelFtpEditor : openFtpEditor}
                disabled={isLoadingFtp || isSavingFtp}
              >
                {!ftpEditing ? <FiEdit3 size={14} /> : null}
                {ftpEditing
                  ? "Cancel"
                  : ftpSettings.enabled
                  ? "Edit FTP"
                  : "Set up FTP"}
              </button>
            </div>
          </div>

          <div className="space-y-5">
            {isLoadingFtp ? (
              <div className="text-sm settings-secondary">
                Loading FTP settings...
              </div>
            ) : !ftpEditing ? (
              <>
                {ftpSettings?.url ? (
                  <div className="rounded-md settings-muted-surface p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-medium settings-secondary">
                          FTP URL
                        </p>
                        <p className="mt-1 truncate text-sm font-medium settings-foreground">
                          {ftpSettings.url}
                        </p>
                      </div>
                      <button
                        type="button"
                        className="settings-button"
                        onClick={handleCopyFtpUrl}
                      >
                        <FiCopy size={14} />
                        Copy
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-md settings-muted-surface p-4 text-sm settings-secondary">
                    Configure FTP credentials to generate a client URL.
                  </div>
                )}

              </>
            ) : (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-md settings-muted-surface p-4">
                  <div>
                    <p className="text-xs font-medium settings-secondary">
                      FTP access
                    </p>
                    <p className="mt-1 text-sm font-medium settings-foreground">
                      {ftpForm.enabled
                        ? ftpSettings.enabled
                          ? "Enabled"
                          : "Will be enabled after saving"
                        : ftpSettings.enabled
                        ? "Will be disabled after saving"
                        : "Disabled"}
                    </p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={ftpForm.enabled}
                    className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border p-0.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 disabled:cursor-not-allowed disabled:opacity-60 ${
                      ftpForm.enabled
                        ? "border-blue-500/40 bg-blue-600/75 dark:border-blue-400/30 dark:bg-blue-500/55"
                        : "border-neutral-300 bg-neutral-200 settings-border dark:bg-[#2a2b2f]"
                    }`}
                    onClick={() =>
                      setFtpForm((currentForm) => ({
                        ...currentForm,
                        enabled: !currentForm.enabled,
                      }))
                    }
                    disabled={isSavingFtp}
                    title={ftpForm.enabled ? "Disable FTP" : "Enable FTP"}
                  >
                    <span
                      className={`inline-block h-5 w-5 rounded-full bg-white shadow-sm ring-1 ring-black/10 transition-transform dark:bg-neutral-100 ${
                        ftpForm.enabled ? "translate-x-5" : "translate-x-0"
                      }`}
                    />
                    <span className="sr-only">
                      {ftpForm.enabled ? "Disable FTP" : "Enable FTP"}
                    </span>
                  </button>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 rounded-md settings-muted-surface p-4">
                  <div>
                    <p className="text-sm font-medium settings-foreground">
                      Use parsed folder names
                    </p>
                    <p className="mt-1 text-xs settings-secondary">
                      Show movie titles with the last part of the hash instead of
                      hash directories.
                    </p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={ftpForm.friendly_names}
                    className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border p-0.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 disabled:cursor-not-allowed disabled:opacity-60 ${
                      ftpForm.friendly_names
                        ? "border-blue-500/40 bg-blue-600/75 dark:border-blue-400/30 dark:bg-blue-500/55"
                        : "border-neutral-300 bg-neutral-200 settings-border dark:bg-[#2a2b2f]"
                    }`}
                    onClick={() =>
                      setFtpForm((currentForm) => ({
                        ...currentForm,
                        friendly_names: !currentForm.friendly_names,
                      }))
                    }
                    disabled={isSavingFtp}
                    title={
                      ftpForm.friendly_names
                        ? "Use parsed folder names"
                        : "Use real hash directories"
                    }
                  >
                    <span
                      className={`inline-block h-5 w-5 rounded-full bg-white shadow-sm ring-1 ring-black/10 transition-transform dark:bg-neutral-100 ${
                        ftpForm.friendly_names
                          ? "translate-x-5"
                          : "translate-x-0"
                      }`}
                    />
                    <span className="sr-only">
                      {ftpForm.friendly_names
                        ? "Disable parsed folder names"
                        : "Enable parsed folder names"}
                    </span>
                  </button>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <label className="block">
                    <span className="text-xs font-medium settings-secondary">
                      FTP username
                    </span>
                    <input
                      className={accountInputClass}
                      value={ftpForm.username}
                      placeholder="Choose FTP username"
                      onChange={(event) =>
                        setFtpForm((currentForm) => ({
                          ...currentForm,
                          username: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium settings-secondary">
                      FTP password
                    </span>
                    <div className="relative">
                      <input
                        type={passwordVisibility.ftp ? "text" : "password"}
                        className={passwordInputClass}
                        value={ftpForm.password}
                        placeholder={
                          ftpSettings.has_password
                            ? "Enter saved FTP password"
                            : "Set FTP password"
                        }
                        onChange={(event) =>
                          setFtpForm((currentForm) => ({
                            ...currentForm,
                            password: event.target.value,
                          }))
                        }
                      />
                      {renderPasswordToggle("ftp", passwordVisibility.ftp)}
                    </div>
                    {ftpSettings.has_password && !ftpSettings.password ? (
                      <p className="mt-1 text-xs settings-secondary">
                        Re-enter your current password once to make it available
                        here for future edits.
                      </p>
                    ) : null}
                  </label>
                </div>

                <div className="flex items-center justify-end gap-2 border-t border-neutral-100 pt-4 settings-border">
                  <button
                    type="button"
                    className="settings-button"
                    onClick={cancelFtpEditor}
                    disabled={isSavingFtp}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="whitespace-nowrap rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={handleSaveFtpSettings}
                    disabled={isSavingFtp}
                  >
                    {isSavingFtp ? "Saving..." : "Save FTP settings"}
                  </button>
                </div>
              </>
            )}
          </div>
        </section>

        <div hidden={settingsCategory!=="links"}>{renderPublicUrlsSection()}</div>

        <section hidden={settingsCategory!=="sessions"} className={settingsPanelClass}>
          <div
            className="settings-section-heading"
          >
            <div>
              <p className="text-sm font-semibold settings-foreground">
                Active sessions
              </p>
              <p className="mt-1 text-sm settings-secondary">
                Review devices that are signed in and revoke access when needed.
              </p>
            </div>
            <button
              type="button"
              className="settings-button"
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
          <div className="settings-toolbar">
            <label className="settings-search"><FiSearch size={18} aria-hidden="true"/><input type="search" aria-label="Search sessions" placeholder="Search devices or IP addresses" value={sessionQuery} onChange={event=>setSessionQuery(event.target.value)}/></label>
            <select aria-label="Filter sessions" value={sessionFilter} onChange={event=>setSessionFilter(event.target.value)} className="settings-select"><option value="all">All devices</option><option value="current">This device</option><option value="other">Other devices</option></select>
          </div>
          <div className="settings-divided-list">
            {isLoadingSessions ? (
              <div className="px-5 py-6 text-sm settings-secondary">
                Loading sessions...
              </div>
            ) : visibleSessions.length ? (
              visibleSessions.map((session) => (
                <div
                  key={session.id}
                  className="settings-device-row"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-medium settings-foreground">
                        {session.device_name}
                      </p>
                      {session.current ? (
                        <span className="rounded border border-neutral-200 px-1.5 py-0.5 text-[10px] font-medium text-neutral-600 dark:border-neutral-700 dark:text-neutral-300">
                          Current
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs settings-secondary">
                      {session.ip || "Unknown IP"} · Last active{" "}
                      {formatRelativeTime(session.last_accessed_at, Date.now())}
                    </p>
                    <p className="mt-1 text-xs settings-secondary dark:settings-secondary">
                      Created {formatCreatedAt(session.created_at)}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="settings-button"
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
              <div className="px-5 py-6 text-sm settings-secondary">
                No sessions match your search.
              </div>
            )}
          </div>
          <div className="settings-pagination">
            <span>{filteredSessionCount} session{filteredSessionCount===1?"":"s"} · Page {Math.min(sessionPage,sessionPageCount)} of {sessionPageCount}</span>
            <div className="flex gap-2"><button type="button" className="settings-button" disabled={sessionPage<=1} onClick={()=>setSessionPage(page=>page-1)}>Previous</button><button type="button" className="settings-button" disabled={sessionPage>=sessionPageCount} onClick={()=>setSessionPage(page=>page+1)}>Next</button></div>
          </div>
        </section>
          </div>
        </div>
      </div>

      {sessionPendingSignOut ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 backdrop-blur-[1px]">
          <div className="w-full max-w-sm rounded-lg border border-neutral-200 bg-white p-4 shadow-lg settings-border dark:bg-[#202124]">
            <p className="text-sm font-semibold settings-foreground">
              {sessionPendingSignOut.current
                ? "Sign out current session?"
                : "Sign out this session?"}
            </p>
            <p className="mt-2 text-sm leading-6 settings-secondary">
              {sessionPendingSignOut.current
                ? "You will be signed out of this browser."
                : "That device will need to sign in again."}
            </p>
            <div className="mt-4 rounded-md bg-neutral-50 px-3 py-2 dark:bg-[#18191b]">
              <p className="truncate text-sm font-medium settings-foreground">
                {sessionPendingSignOut.device_name}
              </p>
              <p className="mt-1 truncate text-xs settings-secondary">
                {sessionPendingSignOut.ip || "Unknown IP"}
              </p>
            </div>
            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                type="button"
                className="rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-600 transition-colors hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60 settings-border dark:text-neutral-300 dark:hover:bg-[#2a2b2f]"
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

      {confirmDeleteAllPublicUrls ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 backdrop-blur-[1px]">
          <div className="w-full max-w-sm rounded-lg border border-neutral-200 bg-white p-4 shadow-lg settings-border dark:bg-[#202124]">
            <p className="text-sm font-semibold settings-foreground">
              Delete all public URLs?
            </p>
            <p className="mt-2 text-sm leading-6 settings-secondary">
              All active public file links will stop working for clients.
            </p>
            <div className="mt-4 rounded-md bg-neutral-50 px-3 py-2 dark:bg-[#18191b]">
              <p className="text-sm font-medium settings-foreground">
                {publicUrlsTotal} active public URLs
              </p>
            </div>
            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                type="button"
                className="rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-600 transition-colors hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60 settings-border dark:text-neutral-300 dark:hover:bg-[#2a2b2f]"
                onClick={() => setConfirmDeleteAllPublicUrls(false)}
                disabled={deactivatingPublicUrl === "__all__"}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-md bg-red-500 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-red-600 dark:hover:bg-red-500"
                onClick={() => handleBulkDeletePublicUrls({ all: true })}
                disabled={deactivatingPublicUrl === "__all__"}
              >
                {deactivatingPublicUrl === "__all__"
                  ? "Deleting..."
                  : "Delete all"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

    </div>
  );
}
