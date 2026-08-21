"use client";

import DocumentUpload from "@/components/DocumentUpload";
import LabResultsForm from "@/components/LabResultsForm";
import PatientAuditTrail from "@/components/PatientAuditTrail";
import PatientTimeline from "@/components/PatientTimeline";

export default function PatientRecordsTab() {
  return (
    <div className="space-y-6 pt-4">
      <LabResultsForm />
      <DocumentUpload />
      <PatientTimeline />
      <PatientAuditTrail />
    </div>
  );
}
