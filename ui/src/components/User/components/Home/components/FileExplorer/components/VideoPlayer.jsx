import React from "react";
import { Modal } from "@mantine/core";

export default function VideoPlayer({ open, url, name, onClose }) {
  return (
    <Modal
      opened={open}
      onClose={onClose}
      title={name}
      size="xl"
      centered
    >
      <video className="w-full" controls autoPlay src={url}>
        Your browser does not support the video tag.
      </video>
    </Modal>
  );
}
