import type { IconName } from '@/ui/kit';

/** The four steps of a claim. Shared by onboarding and the "How it works" screen so they never drift apart. */
export const JOURNEY: { icon: IconName; title: string; how: string }[] = [
  {
    icon: 'document-text-outline',
    title: 'Add your policy',
    how: 'Upload the policy PDF or a photo, pick one you bought on Paytm, or type the policy number. We explain your cover in plain words.',
  },
  {
    icon: 'medkit-outline',
    title: 'In hospital? Check before you leave',
    how: 'Tell us the room and the treatment by voice, chat or a short form. We show what the insurer is likely to cut while you can still change it.',
  },
  {
    icon: 'cloud-upload-outline',
    title: 'Add papers and file the claim',
    how: 'Upload the bill and discharge summary. Let us fill the form, or fill it yourself. We check it as you go and show what you will likely get.',
  },
  {
    icon: 'cash-outline',
    title: 'Track it and get paid',
    how: 'Follow the claim here. If money is cut or the claim is rejected, we explain why and draft your appeal. Need cash meanwhile? A partner lender may offer a bridge loan.',
  },
];

export const KEEP_READY = [
  'Your policy: the PDF, a photo, or just the policy number',
  'Hospital papers: final bill, discharge summary, prescriptions, lab reports',
  'Bank details for the payout: a cancelled cheque photo is enough',
];
