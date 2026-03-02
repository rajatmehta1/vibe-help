import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

const STORAGE_KEY = "forgeline_notification_prefs";

interface Prefs {
  scanComplete: boolean;
  violationsFound: boolean;
  indexComplete: boolean;
}

const defaults: Prefs = {
  scanComplete: true,
  violationsFound: true,
  indexComplete: true,
};

function loadPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...defaults, ...JSON.parse(raw) };
  } catch {
    // ignore
  }
  return defaults;
}

export default function NotificationPrefs() {
  const [prefs, setPrefs] = useState<Prefs>(defaults);

  useEffect(() => {
    setPrefs(loadPrefs());
  }, []);

  const update = useCallback(
    (key: keyof Prefs, value: boolean) => {
      const next = { ...prefs, [key]: value };
      setPrefs(next);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      toast.success("Notification preference updated");
    },
    [prefs],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Notification Preferences</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          These preferences are stored locally in your browser.
        </p>
        <div className="flex items-center justify-between">
          <Label>Scan completed</Label>
          <Switch
            checked={prefs.scanComplete}
            onCheckedChange={(v) => update("scanComplete", v)}
          />
        </div>
        <div className="flex items-center justify-between">
          <Label>Violations found</Label>
          <Switch
            checked={prefs.violationsFound}
            onCheckedChange={(v) => update("violationsFound", v)}
          />
        </div>
        <div className="flex items-center justify-between">
          <Label>Indexing completed</Label>
          <Switch
            checked={prefs.indexComplete}
            onCheckedChange={(v) => update("indexComplete", v)}
          />
        </div>
      </CardContent>
    </Card>
  );
}
