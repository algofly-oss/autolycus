import AddTorrent from "./components/AddTorrent";

export default function Home() {
  return (
    <div className="flex justify-center">
      <div className="m-4 pb-16 md:pb-6 xl:m-8 relative overflow-y-auto overflow-x-hidden 2xl:w-[80rem] w-full">
        <AddTorrent />
      </div>
    </div>
  );
}
