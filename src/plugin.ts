import type { Plugin } from '@elizaos/core';
import {
  type Action,
  type ActionResult,
  type Content,
  type GenerateTextParams,
  type HandlerCallback,
  type IAgentRuntime,
  type Memory,
  ModelType,
  type Provider,
  type ProviderResult,
  Service,
  type State,
  logger,
} from '@elizaos/core';
import { z } from 'zod';
import * as fs from 'fs';
import * as path from 'path';
import { spawn } from 'child_process';

/**
 * Define the configuration schema for the plugin with the following properties:
 *
 * @param {string} EXAMPLE_PLUGIN_VARIABLE - The name of the plugin (min length of 1, optional)
 * @returns {object} - The configured schema object
 */
const configSchema = z.object({
  EXAMPLE_PLUGIN_VARIABLE: z
    .string()
    .min(1, 'Example plugin variable is not provided')
    .optional()
    .transform((val) => {
      if (!val) {
        console.warn('Warning: Example plugin variable is not provided');
      }
      return val;
    }),
});

/**
 * Example HelloWorld action
 * This demonstrates the simplest possible action structure
 */
/**
 * Represents an action that responds with a simple hello world message.
 *
 * @typedef {Object} Action
 * @property {string} name - The name of the action
 * @property {string[]} similes - The related similes of the action
 * @property {string} description - Description of the action
 * @property {Function} validate - Validation function for the action
 * @property {Function} handler - The function that handles the action
 * @property {Object[]} examples - Array of examples for the action
 */
const helloWorldAction: Action = {
  name: 'HELLO_WORLD',
  similes: ['GREET', 'SAY_HELLO'],
  description: 'Responds with a simple hello world message',

  validate: async (_runtime: IAgentRuntime, _message: Memory, _state: State): Promise<boolean> => {
    // Always valid
    return true;
  },

  handler: async (
    _runtime: IAgentRuntime,
    message: Memory,
    _state: State,
    _options: any,
    callback: HandlerCallback,
    _responses: Memory[]
  ): Promise<ActionResult> => {
    try {
      logger.info('Handling HELLO_WORLD action');

      // Simple response content
      const responseContent: Content = {
        text: 'hello world!',
        actions: ['HELLO_WORLD'],
        source: message.content.source,
      };

      // Call back with the hello world message
      await callback(responseContent);

      return {
        text: 'Sent hello world greeting',
        values: {
          success: true,
          greeted: true,
        },
        data: {
          actionName: 'HELLO_WORLD',
          messageId: message.id,
          timestamp: Date.now(),
        },
        success: true,
      };
    } catch (error) {
      logger.error({ error }, 'Error in HELLO_WORLD action:');

      return {
        text: 'Failed to send hello world greeting',
        values: {
          success: false,
          error: 'GREETING_FAILED',
        },
        data: {
          actionName: 'HELLO_WORLD',
          error: error instanceof Error ? error.message : String(error),
        },
        success: false,
        error: error instanceof Error ? error : new Error(String(error)),
      };
    }
  },

  examples: [
    [
      {
        name: '{{name1}}',
        content: {
          text: 'Can you say hello?',
        },
      },
      {
        name: '{{name2}}',
        content: {
          text: 'hello world!',
          actions: ['HELLO_WORLD'],
        },
      },
    ],
  ],
};

/**
 * Example Hello World Provider
 * This demonstrates the simplest possible provider implementation
 */
const helloWorldProvider: Provider = {
  name: 'HELLO_WORLD_PROVIDER',
  description: 'A simple example provider',

  get: async (
    _runtime: IAgentRuntime,
    _message: Memory,
    _state: State
  ): Promise<ProviderResult> => {
    return {
      text: 'I am a provider',
      values: {},
      data: {},
    };
  },
};

/**
 * Download Image Action
 * This action automatically downloads images from Discord messages and saves them locally
 */
const downloadImageAction: Action = {
  name: 'DOWNLOAD_IMAGE',
  similes: ['SAVE_IMAGE', 'STORE_IMAGE', 'GET_IMAGE', 'DOWNLOAD_IMAGES'],
  description: 'Downloads images from Discord messages and saves them to local storage',

  validate: async (_runtime: IAgentRuntime, message: Memory, _state: State): Promise<boolean> => {
    // Debug logging
    logger.info('DOWNLOAD_IMAGE validation - checking message');
    logger.info({
      hasAttachments: !!message.content.attachments,
      attachmentsLength: message.content.attachments?.length || 0,
      attachments: message.content.attachments
    }, 'Message attachments info');

    // Check if message has attachments
    if (!message.content.attachments || message.content.attachments.length === 0) {
      logger.info('No attachments found in message');
      return false;
    }

    // Check if any attachment is an image
    // After Discord plugin processing, images have source: "Image"
    const hasImage = message.content.attachments.some(
      (attachment: any) => {
        const isImage = attachment.source === 'Image' ||
                       attachment.contentType?.startsWith('image/') ||
                       attachment.url?.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/i);
        logger.info({ attachment, isImage }, 'Checking attachment');
        return isImage;
      }
    );

    logger.info({ hasImage }, 'Validation result');
    return hasImage;
  },

  handler: async (
    _runtime: IAgentRuntime,
    message: Memory,
    _state: State,
    _options: any,
    callback: HandlerCallback,
    _responses: Memory[]
  ): Promise<ActionResult> => {
    try {
      logger.info('Handling DOWNLOAD_IMAGE action');

      // Get image attachments
      const imageAttachments = message.content.attachments?.filter(
        (attachment: any) =>
          attachment.source === 'Image' ||
          attachment.contentType?.startsWith('image/') ||
          attachment.url?.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/i)
      ) || [];

      if (imageAttachments.length === 0) {
        return {
          text: 'No images found in message',
          values: { success: false },
          data: { actionName: 'DOWNLOAD_IMAGE' },
          success: false,
        };
      }

      // Create temp_images directory if it doesn't exist
      const downloadDir = path.join(process.cwd(), 'temp_images');
      if (!fs.existsSync(downloadDir)) {
        fs.mkdirSync(downloadDir, { recursive: true });
        logger.info(`Created directory: ${downloadDir}`);
      }

      const downloadedFiles: string[] = [];
      const errors: string[] = [];

      // Download each image
      for (const attachment of imageAttachments) {
        try {
          const imageUrl = attachment.url;
          if (!imageUrl) {
            logger.warn({ attachment }, 'Attachment missing URL, skipping');
            continue;
          }

          // Generate filename from title, name, or URL
          let fileName = attachment.title || attachment.name;
          if (!fileName) {
            // Extract filename from URL
            const urlPath = new URL(imageUrl).pathname;
            fileName = urlPath.split('/').pop() || `image_${attachment.id}`;
          }

          // Ensure filename has an extension
          if (!fileName.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/i)) {
            const ext = attachment.contentType?.split('/')[1] || 'png';
            fileName = `${fileName}.${ext}`;
          }

          // Sanitize filename
          fileName = fileName.replace(/[^a-zA-Z0-9._-]/g, '_');

          const filePath = path.join(downloadDir, fileName);

          logger.info(`Downloading image from: ${imageUrl} to ${fileName}`);

          // Fetch the image
          const response = await fetch(imageUrl);
          if (!response.ok) {
            throw new Error(`Failed to fetch image: ${response.statusText}`);
          }

          // Get the image buffer
          const arrayBuffer = await response.arrayBuffer();
          const buffer = Buffer.from(arrayBuffer);

          // Save to file
          fs.writeFileSync(filePath, buffer);
          downloadedFiles.push(fileName);

          logger.info(`Saved image to: ${filePath}`);
        } catch (error) {
          const errorMsg = error instanceof Error ? error.message : String(error);
          const attachmentName = attachment.title || attachment.name || attachment.id;
          logger.error(`Error downloading image ${attachmentName}: ${errorMsg}`);
          errors.push(`${attachmentName}: ${errorMsg}`);
        }
      }

      // Prepare response message
      let responseText = '';
      if (downloadedFiles.length > 0) {
        responseText = `Successfully downloaded ${downloadedFiles.length} image(s):\n${downloadedFiles.map(f => `- ${f}`).join('\n')}`;
      }
      if (errors.length > 0) {
        responseText += `\n\nFailed to download ${errors.length} image(s):\n${errors.join('\n')}`;
      }

      const responseContent: Content = {
        text: responseText,
        actions: ['DOWNLOAD_IMAGE'],
        source: message.content.source,
      };

      // Only send callback if it exists (might not be present in event handlers)
      if (callback) {
        await callback(responseContent);
      }

      return {
        text: `Downloaded ${downloadedFiles.length} images`,
        values: {
          success: true,
          downloadedCount: downloadedFiles.length,
          failedCount: errors.length,
        },
        data: {
          actionName: 'DOWNLOAD_IMAGE',
          downloadedFiles,
          errors,
          downloadPath: downloadDir,
        },
        success: true,
      };
    } catch (error) {
      logger.error({ error }, 'Error in DOWNLOAD_IMAGE action:');

      if (callback) {
        await callback({
          text: 'Failed to download images',
          error: true,
        });
      }

      return {
        text: 'Failed to download images',
        values: {
          success: false,
          error: 'DOWNLOAD_FAILED',
        },
        data: {
          actionName: 'DOWNLOAD_IMAGE',
          error: error instanceof Error ? error.message : String(error),
        },
        success: false,
        error: error instanceof Error ? error : new Error(String(error)),
      };
    }
  },

  examples: [
    [
      {
        name: '{{name1}}',
        content: {
          text: 'Here is an image',
          attachments: [
            {
              id: 'img123',
              name: 'example.png',
              url: 'https://example.com/image.png',
              contentType: 'image/png',
            },
          ],
        },
      },
      {
        name: '{{name2}}',
        content: {
          text: 'Successfully downloaded 1 image(s):\n- example.png',
          actions: ['DOWNLOAD_IMAGE'],
        },
      },
    ],
  ],
};

/**
 * Helper function to run Chronos pipeline and parse results
 */
async function runChronosPipeline(imagePath: string, userId: string): Promise<{ questions: string[]; answers: string[] } | null> {
  return new Promise((resolve) => {
    const cwd = process.cwd();
    const env = { ...process.env };
    const chronosScript = path.join(cwd, 'chronos', 'discord_main.py');

    // Use conda heritage environment Python
    const pythonCmd = '/home/sidharth/miniconda3/envs/heritage/bin/python';
    const args = [chronosScript, imagePath, userId];

    logger.info(`Running Chronos pipeline: ${pythonCmd} ${chronosScript} ${imagePath} ${userId}`);

    // Log environment variables being passed
    logger.info(`ENV check - OPENAI_API_KEY: ${env.OPENAI_API_KEY?.substring(0, 20)}...`);
    logger.info(`ENV check - GOOGLE_API_KEY: ${env.GOOGLE_API_KEY?.substring(0, 20)}...`);

    const childProcess = spawn(pythonCmd, args, {
      cwd: cwd,
      env: env,
    });

    let stdout = '';
    let stderr = '';

    childProcess.stdout.on('data', (data) => {
      const output = data.toString();
      stdout += output;
      // Log Python output for debugging
      logger.info(`[Chronos] ${output.trim()}`);
    });

    childProcess.stderr.on('data', (data) => {
      const output = data.toString();
      stderr += output;
      logger.warn(`[Chronos Error] ${output.trim()}`);
    });

    childProcess.on('close', (code) => {
      logger.info(`Chronos pipeline exited with code ${code}`);

      if (code !== 0) {
        logger.error(`Chronos pipeline failed with exit code ${code}`);
        logger.error(`stderr: ${stderr}`);
        resolve(null);
        return;
      }

      // Parse results from stdout
      const results = parseChronosResults(stdout);
      resolve(results);
    });

    childProcess.on('error', (error) => {
      logger.error({ error }, 'Failed to spawn Chronos process - check if heritage conda environment exists');
      resolve(null);
    });
  });
}

/**
 * Parse Chronos results from stdout
 */
function parseChronosResults(stdout: string): { questions: string[]; answers: string[] } | null {
  try {
    // Find the results block between markers
    const startMarker = 'DISCORD_RESULTS_START';
    const endMarker = 'DISCORD_RESULTS_END';

    const startIndex = stdout.indexOf(startMarker);
    const endIndex = stdout.indexOf(endMarker);

    if (startIndex === -1 || endIndex === -1) {
      logger.error('No DISCORD_RESULTS block found in output');
      return null;
    }

    const resultsBlock = stdout.substring(startIndex + startMarker.length, endIndex);
    const lines = resultsBlock.split('\n').filter((line) => line.trim() !== '' && line !== '---' && !line.startsWith('='));

    const questions: string[] = [];
    const answers: string[] = [];

    for (const line of lines) {
      if (line.includes('QUESTION_') && line.includes(':::')) {
        const question = line.split(':::')[1]?.trim();
        if (question) questions.push(question);
      } else if (line.includes('ANSWER_') && line.includes(':::')) {
        const answer = line.split(':::')[1]?.trim();
        if (answer) answers.push(answer);
      }
    }

    logger.info(`Parsed ${questions.length} questions and ${answers.length} answers`);
    return { questions, answers };
  } catch (error) {
    logger.error({ error }, 'Failed to parse Chronos results');
    return null;
  }
}

/**
 * Split long message into chunks for Discord's 2000 character limit
 */
function splitDiscordMessage(text: string, maxLength: number = 1900): string[] {
  if (text.length <= maxLength) {
    return [text];
  }

  const chunks: string[] = [];
  const lines = text.split('\n');
  let currentChunk = '';

  for (const line of lines) {
    if ((currentChunk + line + '\n').length > maxLength) {
      if (currentChunk) {
        chunks.push(currentChunk.trim());
        currentChunk = '';
      }

      // If a single line is too long, split it by sentences
      if (line.length > maxLength) {
        const sentences = line.match(/[^.!?]+[.!?]+/g) || [line];
        for (const sentence of sentences) {
          if ((currentChunk + sentence).length > maxLength) {
            if (currentChunk) {
              chunks.push(currentChunk.trim());
            }
            currentChunk = sentence;
          } else {
            currentChunk += sentence;
          }
        }
      } else {
        currentChunk = line + '\n';
      }
    } else {
      currentChunk += line + '\n';
    }
  }

  if (currentChunk) {
    chunks.push(currentChunk.trim());
  }

  return chunks;
}

export class StarterService extends Service {
  static serviceType = 'starter';
  capabilityDescription =
    'This is a starter service which is attached to the agent through the starter plugin.';

  constructor(runtime: IAgentRuntime) {
    super(runtime);
  }

  static async start(runtime: IAgentRuntime) {
    logger.info('*** Starting starter service ***');
    const service = new StarterService(runtime);
    return service;
  }

  static async stop(runtime: IAgentRuntime) {
    logger.info('*** Stopping starter service ***');
    // get the service from the runtime
    const service = runtime.getService(StarterService.serviceType);
    if (!service) {
      throw new Error('Starter service not found');
    }
    service.stop();
  }

  async stop() {
    logger.info('*** Stopping starter service instance ***');
  }
}

const plugin: Plugin = {
  name: 'starter',
  description: 'A starter plugin for Eliza',
  // Set lowest priority so real models take precedence
  priority: -1000,
  config: {
    EXAMPLE_PLUGIN_VARIABLE: process.env.EXAMPLE_PLUGIN_VARIABLE,
  },
  async init(config: Record<string, string>) {
    logger.info('*** Initializing starter plugin ***');
    try {
      const validatedConfig = await configSchema.parseAsync(config);

      // Set all environment variables at once
      for (const [key, value] of Object.entries(validatedConfig)) {
        if (value) process.env[key] = value;
      }
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new Error(
          `Invalid plugin configuration: ${error.errors.map((e) => e.message).join(', ')}`
        );
      }
      throw error;
    }
  },
  models: {
    [ModelType.TEXT_SMALL]: async (
      _runtime,
      { prompt, stopSequences = [] }: GenerateTextParams
    ) => {
      return 'Never gonna give you up, never gonna let you down, never gonna run around and desert you...';
    },
    [ModelType.TEXT_LARGE]: async (
      _runtime,
      {
        prompt,
        stopSequences = [],
        maxTokens = 8192,
        temperature = 0.7,
        frequencyPenalty = 0.7,
        presencePenalty = 0.7,
      }: GenerateTextParams
    ) => {
      return 'Never gonna make you cry, never gonna say goodbye, never gonna tell a lie and hurt you...';
    },
  },
  routes: [
    {
      name: 'helloworld',
      path: '/helloworld',
      type: 'GET',
      handler: async (_req: any, res: any) => {
        // send a response
        res.json({
          message: 'Hello World!',
        });
      },
    },
  ],
  events: {
    MESSAGE_RECEIVED: [
      async (params) => {
        logger.info('MESSAGE_RECEIVED event received');
        logger.info({ keys: Object.keys(params) }, 'MESSAGE_RECEIVED param keys');

        const { runtime, message, callback } = params;

        // Check if message has image attachments
        if (message?.content?.attachments && message.content.attachments.length > 0) {
          logger.info('MESSAGE_RECEIVED: Found attachments, checking for images');

          const imageAttachments = message.content.attachments.filter(
            (attachment: any) =>
              attachment.source === 'Image' ||
              attachment.contentType?.startsWith('image/') ||
              attachment.url?.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/i)
          );

          if (imageAttachments.length > 0) {
            logger.info(`MESSAGE_RECEIVED: ${imageAttachments.length} image(s) detected`);

            // Process each image through Chronos pipeline
            for (const attachment of imageAttachments) {
              try {
                // Step 1: Download the image to temp_images/
                const tempDir = path.join(process.cwd(), 'temp_images');
                if (!fs.existsSync(tempDir)) {
                  fs.mkdirSync(tempDir, { recursive: true });
                }

                const imageUrl = attachment.url;
                if (!imageUrl) {
                  logger.warn('Attachment missing URL, skipping');
                  continue;
                }

                // Generate filename
                let fileName = attachment.title || (attachment as any).name;
                if (!fileName) {
                  const urlPath = new URL(imageUrl).pathname;
                  fileName = urlPath.split('/').pop() || `image_${attachment.id}`;
                }

                // Ensure extension
                if (!fileName.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/i)) {
                  const ext = attachment.contentType?.split('/')[1] || 'png';
                  fileName = `${fileName}.${ext}`;
                }

                fileName = fileName.replace(/[^a-zA-Z0-9._-]/g, '_');
                const imagePath = path.join(tempDir, fileName);

                // Download image
                logger.info(`Downloading image to: ${imagePath}`);
                const response = await fetch(imageUrl);
                if (!response.ok) {
                  throw new Error(`Failed to fetch image: ${response.statusText}`);
                }

                const arrayBuffer = await response.arrayBuffer();
                const buffer = Buffer.from(arrayBuffer);
                fs.writeFileSync(imagePath, buffer);
                logger.info(`Image saved successfully`);

                // Step 2: Extract user ID from message
                const userId = message.entityId || 'discord_user';

                // Step 3: Run Chronos pipeline
                logger.info('Starting Chronos pipeline processing...');
                const results = await runChronosPipeline(imagePath, userId);

                if (!results || results.questions.length === 0) {
                  logger.error('Chronos pipeline returned no results');
                  if (callback) {
                    await callback({
                      text: '⚠️ Failed to process image. Please check the logs for details.',
                      source: message.content.source,
                    });
                  }
                  continue;
                }

                // Step 4: Format and send results
                logger.info(`Formatting ${results.questions.length} results for Discord`);

                let responseText = '🔬 **Chronos Analysis Results**\n\n';

                for (let i = 0; i < results.questions.length; i++) {
                  responseText += `**Q${i + 1}:** ${results.questions[i]}\n\n`;
                  responseText += `**A${i + 1}:** ${results.answers[i]}\n\n`;
                  responseText += '---\n\n';
                }

                // Split message if needed for Discord's 2000 char limit
                const messageChunks = splitDiscordMessage(responseText);

                logger.info(`Sending ${messageChunks.length} message chunk(s) to Discord`);

                // Send each chunk
                if (callback) {
                  for (const chunk of messageChunks) {
                    await callback({
                      text: chunk,
                      source: message.content.source,
                    });
                  }
                }

                // Cleanup: Delete temp image after processing
                try {
                  fs.unlinkSync(imagePath);
                  logger.info(`Deleted temp image: ${imagePath}`);
                } catch (cleanupError) {
                  logger.warn({ cleanupError }, 'Failed to delete temp image');
                }

              } catch (error) {
                logger.error({ error }, 'Error processing image through Chronos');
                if (callback) {
                  await callback({
                    text: '❌ An error occurred while processing the image.',
                    source: message.content.source,
                  });
                }
              }
            }
          }
        }
      },
    ],
    VOICE_MESSAGE_RECEIVED: [
      async (params) => {
        logger.info('VOICE_MESSAGE_RECEIVED event received');
        // print the keys
        logger.info({ keys: Object.keys(params) }, 'VOICE_MESSAGE_RECEIVED param keys');
      },
    ],
    WORLD_CONNECTED: [
      async (params) => {
        logger.info('WORLD_CONNECTED event received');
        // print the keys
        logger.info({ keys: Object.keys(params) }, 'WORLD_CONNECTED param keys');
      },
    ],
    WORLD_JOINED: [
      async (params) => {
        logger.info('WORLD_JOINED event received');
        // print the keys
        logger.info({ keys: Object.keys(params) }, 'WORLD_JOINED param keys');
      },
    ],
  },
  services: [StarterService],
  actions: [helloWorldAction, downloadImageAction],
  providers: [helloWorldProvider],
};

export default plugin;
