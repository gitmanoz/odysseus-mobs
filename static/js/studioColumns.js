// Center the reading column in the space remaining beside the open Context lane.
export function studioColumns(width, contextOpen = false) {
  width = Math.max(0, Number(width) || 0);
  const margin = Math.min(20, width / 2);
  const gap = 24, basePanel = 320;
  const hasLane = width >= 1040;
  const panel = hasLane ? Math.min(560, Math.max(basePanel, width * .3)) : basePanel;
  const reserved = hasLane && contextOpen ? panel + gap : 0;
  const reading = Math.max(0, Math.min(720, width - margin * 2 - reserved));
  const left = Math.max(margin, (width - reserved - reading) / 2);
  const panelLeft = width - margin - panel;
  return { reading, left, right: Math.max(0, width - left - reading),
    hasLane, panel, panelLeft };
}
