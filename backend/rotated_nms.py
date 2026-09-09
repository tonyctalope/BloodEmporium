"""CPU rotated NMS for YOLOv5-OBB, without a Windows/CUDA extension."""
import math

import cv2
import numpy as np
import torch


def obb_nms(dets, scores, iou_thr, device_id=None):
    is_tensor = isinstance(dets, torch.Tensor)
    boxes = dets.detach().cpu().numpy() if is_tensor else np.asarray(dets)
    confidence = scores.detach().cpu().numpy() if isinstance(scores, torch.Tensor) else np.asarray(scores)
    valid = np.flatnonzero((boxes[:, 2:4] >= 0.001).all(axis=1))
    # YOLOv5-OBB angles rotate counterclockwise in image coordinates; OpenCV uses clockwise degrees.
    rotated = [((float(x), float(y)), (float(w), float(h)), -math.degrees(float(a)))
               for x, y, w, h, a in boxes[valid]]
    polygons = [cv2.boxPoints(box) for box in rotated]
    areas = boxes[valid, 2] * boxes[valid, 3]
    order = np.argsort(-confidence[valid], kind="stable").tolist()
    selected = []
    while order:
        first = order.pop(0)
        selected.append(first)
        remaining = []
        for other in order:
            intersection, _ = cv2.intersectConvexConvex(polygons[first], polygons[other])
            intersection = max(0., min(float(intersection), float(areas[first]), float(areas[other])))
            union = float(areas[first] + areas[other]) - intersection
            if intersection / union <= iou_thr:
                remaining.append(other)
        order = remaining
    # Do not use dnn.NMSBoxesRotated: its full-containment shortcut reports IoU=1
    # even when one edge box is much smaller than the other.
    indices = valid[np.asarray(selected, dtype=np.int64)]
    if is_tensor:
        indices = torch.as_tensor(indices, dtype=torch.long, device=dets.device)
    return dets[indices, :], indices
