export function Empty({ label }: { label: string }) {
  return (
    <div className="rounded border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
      {label}
    </div>
  );
}
