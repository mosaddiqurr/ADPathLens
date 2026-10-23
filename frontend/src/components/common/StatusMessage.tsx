export function StatusMessage({
  message,
  tone = "info",
}: {
  message: string;
  tone?: "info" | "success" | "warning" | "danger";
}) {
  if (!message) return null;
  return (
    <div
      className={`notice notice-${tone}`}
      role={tone === "danger" ? "alert" : "status"}
    >
      {message}
    </div>
  );
}
