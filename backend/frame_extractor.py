import cv2
import os

def extract_frames(video_path, output_dir="storage/frames", interval_seconds=10):
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)

    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps == 0:
        raise Exception("Could not read video FPS")

    frame_interval = int(fps * interval_seconds)

    frame_count = 0
    saved_count = 0

    while True:
        success, frame = cap.read()

        if not success:
            break

        if frame_count % frame_interval == 0:
            timestamp = int(frame_count / fps)

            minutes = timestamp // 60
            seconds = timestamp % 60

            filename = f"{minutes:02d}_{seconds:02d}.jpg"

            cv2.imwrite(
                os.path.join(output_dir, filename),
                frame
            )

            saved_count += 1

        frame_count += 1

    cap.release()

    return {
        "frames_saved": saved_count,
        "output_dir": output_dir
    }


if __name__ == "__main__":
    result = extract_frames(
        "sample_video.mp4",
        interval_seconds=10
    )

    print(result)