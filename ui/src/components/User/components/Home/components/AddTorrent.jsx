import { FiFilePlus } from "react-icons/fi";
import { useState, useRef } from "react";
import axios from "axios";
import apiRoutes from "@/shared/routes/apiRoutes";
import useToast from "@/shared/hooks/useToast";

export default function AddTorrent() {
  const [magnetLink, setMagnetLink] = useState("");
  const fileInput = useRef(null);
  const toast = useToast();

  const addTorrent = async () => {
    if (magnetLink) {
      if (magnetLink.trim().toLowerCase().startsWith("magnet:?xt=urn:btih:")) {
        axios
          .post(apiRoutes.addMagnet, { magnet: magnetLink })
          .then((res) => {
            toast.success("Magnet added");
            setMagnetLink("");
          })
          .catch((err) => {
            toast.error("Unable to add magnet");
          });
      } else if (
        magnetLink.trim().toLowerCase().startsWith("http://") ||
        magnetLink.trim().toLowerCase().startsWith("https://")
      ) {
        axios
          .post(apiRoutes.addDirectDownload, { url: magnetLink })
          .then((res) => {
            toast.success("URL added");
            setMagnetLink("");
          })
          .catch((err) => {
            toast.error("Unable to add URL");
          });
      } else if (
        magnetLink.trim().length === 40 ||
        magnetLink.trim().length === 256
      ) {
        let hash = "magnet:?xt=urn:btih:" + magnetLink.trim();
        axios
          .post(apiRoutes.addMagnet, { magnet: hash })
          .then((res) => {
            toast.success("Magnet added");
            setMagnetLink("");
          })
          .catch((err) => {
            toast.error("Unable to add magnet");
          });
      } else {
        toast.error("Invalid link");
      }
    } else {
      fileInput.current.value = null;
      fileInput.current.click();
    }
  };

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("torrent", file);

    axios
      .post(apiRoutes.addTorrent, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      })
      .then((res) => {
        toast.success("Torrent added");
        fileInput.current.value = null;
      })
      .catch((err) => {
        toast.error("Unable to add torrent");
        fileInput.current.value = null;
      });
  };

  return (
    <div>
      <div className="flex">
        <input
          type="text"
          value={magnetLink}
          placeholder="Magnet Link or Download URL"
          className="text-xs md:text-sm border-0 outline-0 focus:ring-0 rounded-l-lg w-full bg-zinc-100 dark:bg-black pl-4"
          onChange={(e) => setMagnetLink(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              addTorrent();
            }
          }}
        />
        <button
          className="bg-blue-500 dark:bg-blue-700 rounded-r-lg p-4 px-5 -ml-2 text-white active:opacity-90"
          onClick={addTorrent}
        >
          <FiFilePlus size={20} />
        </button>
      </div>
      <input
        ref={fileInput}
        accept=".torrent"
        type="file"
        onChange={handleFileChange}
        className="hidden"
      />
    </div>
  );
}
