import React from "react";

const InfoBlock = ({ title, value }) => (
  <div className="flex-1 bg-neutral-50 dark:bg-[#1d1f23] border dark:border-neutral-800 rounded-lg p-2">
    <h3 className="text-gray-700 dark:text-gray-400">{title}</h3>
    <p className="text-lg text-gray-800 dark:text-white">{value}</p>
  </div>
);

export default InfoBlock;
