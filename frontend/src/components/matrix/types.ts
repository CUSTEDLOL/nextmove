export type Quadrant = "Q1" | "Q2" | "Q3" | "Q4";

export type MappedTask = {
  id: string;
  title: string;
  urgency: number;       // 0–100, higher = more urgent
  importance: number;    // 0–100, higher = more important
  priorityScore: number; // 0–100
  effort: 1 | 2 | 3;
  scheduledToday: boolean;
  quadrant: Quadrant;
};

export type MatrixCanvasProps = {
  tasks: MappedTask[];
  isEditing: boolean;
  onMoveTask: (taskId: string, updates: { urgency: number; importance: number; quadrant: Quadrant }) => void;
  onUpdateTask: (taskId: string, updates: { title: string; effort: 1 | 2 | 3; quadrant: Quadrant }) => void;
  onTopTaskChange?: (taskId: string | null) => void;
};

export type DraggableBubbleProps = {
  task: MappedTask;
  left: number;           // center x coordinate on the board
  top: number;            // center y coordinate on the board
  containerWidth: number;
  containerHeight: number;
  isCritical: boolean;
  isMobile: boolean;
  isEditing: boolean;
  onDrop: (taskId: string, cx: number, cy: number) => void;
  onTap: (taskId: string) => void;
};

export type BubbleSheetProps = {
  task: MappedTask | null;
  onMove: (quadrant: Quadrant) => void;
  onDismiss: () => void;
};
