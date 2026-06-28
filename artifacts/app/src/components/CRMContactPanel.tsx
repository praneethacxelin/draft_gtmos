import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useUpdateContact } from "@/hooks/useContacts";
import { useState, useEffect } from "react";
import { Save, UserCircle, Building2, Linkedin, Mail, Phone, MapPin, Activity } from "lucide-react";

export function CRMContactPanel({
  contact,
  open,
  onOpenChange,
}: {
  contact: any;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const updateContact = useUpdateContact();
  const [formData, setFormData] = useState<any>({});

  useEffect(() => {
    if (contact) {
      setFormData({
        full_name: contact.full_name || "",
        title: contact.title || "",
        email: contact.email || "",
        phone: contact.phone || "",
        linkedin_url: contact.linkedin_url || "",
        persona_type: contact.persona_type || "_none",
        seniority: contact.seniority || "",
      });
    }
  }, [contact]);

  if (!contact) return null;

  const handleSave = () => {
    updateContact.mutate({
      id: contact.id,
      updates: {
        full_name: formData.full_name,
        title: formData.title,
        email: formData.email,
        phone: formData.phone,
        linkedin_url: formData.linkedin_url,
        persona_type: formData.persona_type === "_none" ? null : formData.persona_type,
        seniority: formData.seniority,
      },
    });
    onOpenChange(false);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[400px] sm:w-[540px] overflow-y-auto">
        <SheetHeader className="mb-6">
          <SheetTitle className="flex items-center gap-2 text-xl">
            <UserCircle className="h-6 w-6 text-primary" />
            {contact.full_name || "Unknown Lead"}
          </SheetTitle>
        </SheetHeader>

        <div className="space-y-6">
          <div className="space-y-4 rounded-lg border p-4 bg-muted/20">
            <h3 className="font-medium text-sm flex items-center gap-2">
              <Building2 className="h-4 w-4" /> Account Details
            </h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground text-xs uppercase tracking-wider">Company</p>
                <p className="font-medium">{contact.account_name || "—"}</p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs uppercase tracking-wider">Domain</p>
                <p className="font-medium">{contact.account_domain || "—"}</p>
              </div>
              <div className="col-span-2">
                <p className="text-muted-foreground text-xs uppercase tracking-wider">Industry</p>
                <p className="font-medium">{contact.account_industry || "—"}</p>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="font-medium text-sm">Contact Information</h3>
            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="full_name">Full Name</Label>
                <Input
                  id="full_name"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="title">Job Title</Label>
                <Input
                  id="title"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="email" className="flex items-center gap-1">
                    <Mail className="h-3 w-3" /> Email
                  </Label>
                  <Input
                    id="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="phone" className="flex items-center gap-1">
                    <Phone className="h-3 w-3" /> Phone
                  </Label>
                  <Input
                    id="phone"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  />
                </div>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="linkedin" className="flex items-center gap-1">
                  <Linkedin className="h-3 w-3" /> LinkedIn URL
                </Label>
                <Input
                  id="linkedin"
                  value={formData.linkedin_url}
                  onChange={(e) => setFormData({ ...formData, linkedin_url: e.target.value })}
                />
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="font-medium text-sm">Classification</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>Persona</Label>
                <Select
                  value={formData.persona_type}
                  onValueChange={(val) => setFormData({ ...formData, persona_type: val })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_none">— none —</SelectItem>
                    <SelectItem value="champion">Champion</SelectItem>
                    <SelectItem value="economic_buyer">Economic buyer</SelectItem>
                    <SelectItem value="blocker">Blocker</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>Seniority</Label>
                <Input
                  value={formData.seniority}
                  onChange={(e) => setFormData({ ...formData, seniority: e.target.value })}
                  placeholder="e.g. Director, VP"
                />
              </div>
            </div>
          </div>

          <div className="space-y-4 rounded-lg border p-4 bg-muted/20">
            <h3 className="font-medium text-sm flex items-center gap-2">
              <Activity className="h-4 w-4" /> Campaign & Outreach
            </h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="col-span-2">
                <p className="text-muted-foreground text-xs uppercase tracking-wider">Campaign Name</p>
                <p className="font-medium">{contact.campaign_name || "Unassigned"}</p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs uppercase tracking-wider">Sequence Status</p>
                <p className="font-medium capitalize">{contact.sequence_status || "—"}</p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs uppercase tracking-wider">Emails Sent</p>
                <p className="font-medium">{contact.sent || 0}</p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs uppercase tracking-wider">Replied</p>
                <p className="font-medium">{contact.replied || 0}</p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs uppercase tracking-wider">Bounced</p>
                <p className="font-medium">{contact.bounced || 0}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-8 flex justify-end gap-3">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={updateContact.isPending}>
            <Save className="mr-2 h-4 w-4" />
            Save Changes
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
