export function TypingIndicator() {
  return (
    <div data-typing className="hidden self-start">
      <div className="flex items-center gap-1 rounded-2xl rounded-bl-md bg-[#182533] px-3.5 py-3 shadow-sm shadow-black/25">
        <span data-dot className="size-1.5 rounded-full bg-white" />
        <span data-dot className="size-1.5 rounded-full bg-white" />
        <span data-dot className="size-1.5 rounded-full bg-white" />
      </div>
    </div>
  );
}
