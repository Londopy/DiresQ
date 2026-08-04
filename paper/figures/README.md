# Figures

Empty on purpose. There are no figures yet, and inventing one would be worse
than having none.

## The one figure this paper probably needs

A state diagram of a responder's lifecycle, because §3 describes it in prose and
prose is a bad medium for a state machine:

    joined (ETA stated, 5-240 min)
      -> checked in            [resets the clock, default interval 30 min]
      -> overdue               [interval elapsed with no check-in]
      -> escalated             [SILENT_ESCALATE_MINUTES = 15 after overdue;
                                a report is filed about them, automatically]
      -> cleared               [responder says they are done; not chased]

Two things the diagram should make visible that the prose struggles with:

1. `cleared` is reachable from any state and is *not* a failure — going home is
   not going quiet.
2. Nothing on this diagram is a human decision. That is the argument of the
   paper, and a reader should be able to see it in one glance.

Draw it in TikZ (keeps the source in the repo, no binary blobs) or export a PDF
from a diagram tool and drop it here. `\graphicspath{{figures/}}` is already set
in both wrappers, so `\includegraphics{lifecycle}` will find it.
