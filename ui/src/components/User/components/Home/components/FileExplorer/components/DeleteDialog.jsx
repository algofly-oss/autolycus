import React from "react";
import { Modal, Button, Text } from "@mantine/core";

export default function DeleteDialog({ open, item, onClose, onDelete }) {
  return (
    <Modal
      opened={open}
      onClose={onClose}
      title="Confirm Delete"
      size="sm"
      centered
    >
      <Text size="sm" mb="lg">
        Are you sure you want to delete{" "}
        <strong className="break-all">{item?.name}</strong>?
        {item?.is_directory &&
          " This will delete all contents inside the folder."}
      </Text>
      <div className="flex justify-end gap-4">
        <Button variant="default" onClick={onClose}>
          Cancel
        </Button>
        <Button color="red" onClick={onDelete}>
          Delete
        </Button>
      </div>
    </Modal>
  );
}
